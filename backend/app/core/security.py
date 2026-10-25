"""
StockWise Security & Role-Based Access Control (RBAC) Module.

Provides:
- Fail-closed Supabase JWT token signature and claims verification.
- Trusted role derivation preventing privilege escalation via user_metadata.
- Elimination of demo tokens, role headers, and default-admin fallbacks in production.
- Multi-tenant organization scoping helpers.
- Role-based authorization dependencies (admin, planner, logistics, viewer).
"""

import logging
from typing import List, Optional, Set
from pydantic import BaseModel
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

logger = logging.getLogger("stockwise.security")

security_scheme = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    """Represents a verified authenticated actor."""
    user_id: str
    email: Optional[str] = None
    role: str = "viewer"  # admin, planner, logistics, viewer
    org_id: Optional[str] = None
    is_authenticated: bool = True
    is_demo: bool = False


DEMO_PERSONAS = {
    "admin": AuthenticatedUser(
        user_id="USER-ADMIN-01",
        email="admin@stockwise.internal",
        role="admin",
        org_id="ORG-FMCG-CORP",
        is_authenticated=True,
        is_demo=True,
    ),
    "planner": AuthenticatedUser(
        user_id="USER-PLANNER-01",
        email="planner@stockwise.internal",
        role="planner",
        org_id="ORG-FMCG-CORP",
        is_authenticated=True,
        is_demo=True,
    ),
    "logistics": AuthenticatedUser(
        user_id="USER-LOGISTICS-01",
        email="logistics@stockwise.internal",
        role="logistics",
        org_id="ORG-LOGISTICS-3PL",
        is_authenticated=True,
        is_demo=True,
    ),
    "viewer": AuthenticatedUser(
        user_id="USER-VIEWER-01",
        email="viewer@stockwise.internal",
        role="viewer",
        org_id="ORG-FMCG-CORP",
        is_authenticated=True,
        is_demo=True,
    ),
    "distributor": AuthenticatedUser(
        user_id="USER-DISTRIBUTOR-01",
        email="distributor@stockwise.internal",
        role="distributor",
        org_id="ORG-DIST-WEST",
        is_authenticated=True,
        is_demo=True,
    ),
    "retailer": AuthenticatedUser(
        user_id="USER-RETAILER-01",
        email="retailer@stockwise.internal",
        role="retailer",
        org_id="ORG-RETAIL-METRO",
        is_authenticated=True,
        is_demo=True,
    ),
}

# Known server-side verified user-to-role/org mappings for bootstrap personas
SERVER_VERIFIED_USER_MAPPINGS = {
    "admin@stockwise.internal": {"role": "admin", "org_id": "ORG-FMCG-CORP"},
    "planner@stockwise.internal": {"role": "planner", "org_id": "ORG-FMCG-CORP"},
    "logistics@stockwise.internal": {"role": "logistics", "org_id": "ORG-LOGISTICS-3PL"},
    "viewer@stockwise.internal": {"role": "viewer", "org_id": "ORG-FMCG-CORP"},
    "distributor@stockwise.internal": {"role": "distributor", "org_id": "ORG-DIST-WEST"},
    "retailer@stockwise.internal": {"role": "retailer", "org_id": "ORG-RETAIL-METRO"},
}

PRIVILEGED_ROLES: Set[str] = {"admin", "planner", "logistics", "distributor", "retailer"}


def derive_trusted_role_and_org(payload: dict) -> tuple[str, Optional[str]]:
    """
    Derives role and organization from trusted server-controlled claims.
    CRITICAL SECURITY INVARIANT:
    `user_metadata` in Supabase Auth is client-editable by end-users at signup
    and profile update. Never grant privileged roles ('admin', 'planner', 'logistics',
    'distributor', 'retailer') solely from user_metadata.
    """
    app_metadata = payload.get("app_metadata") or {}
    user_metadata = payload.get("user_metadata") or {}
    email = payload.get("email", "").lower().strip()

    # 1. Check server-side static verified mapping for seed/bootstrap emails
    if email in SERVER_VERIFIED_USER_MAPPINGS:
        mapping = SERVER_VERIFIED_USER_MAPPINGS[email]
        return mapping["role"], mapping["org_id"]

    # 2. Check server-controlled app_metadata (set only via Supabase service_role key)
    server_role = app_metadata.get("role") or payload.get("role")
    server_org = app_metadata.get("org_id")

    if server_role and server_role not in ["authenticated", "anon"]:
        role = str(server_role).lower().strip()
        org_id = str(server_org).strip() if server_org else None
        return role, org_id

    # 3. If only user_metadata has a role, reject self-elevation to privileged roles
    client_role = user_metadata.get("role")
    client_org = user_metadata.get("org_id")

    if client_role:
        client_role_clean = str(client_role).lower().strip()
        if client_role_clean in PRIVILEGED_ROLES:
            logger.warning(
                f"Attempted privilege escalation blocked: user {payload.get('sub')} "
                f"attempted to self-assign privileged role '{client_role_clean}' via user_metadata. "
                "Demoting to 'viewer'."
            )
            return "viewer", str(client_org).strip() if client_org else None
        if client_role_clean == "viewer":
            return "viewer", str(client_org).strip() if client_org else None
        # Any other unknown client-specified role is demoted to viewer
        return "viewer", str(client_org).strip() if client_org else None

    return "viewer", str(client_org).strip() if client_org else None


def verify_supabase_jwt(token: str) -> AuthenticatedUser:
    """
    Decodes and cryptographically verifies a Supabase Auth JWT token.
    Enforces fail-closed signature verification, algorithm restrictions,
    and required claim checks.
    """
    secret = settings.SUPABASE_JWT_SECRET
    is_prod = settings.is_production() or settings.REQUIRE_AUTH

    if not secret:
        if is_prod:
            logger.critical("JWT verification failed-closed: SUPABASE_JWT_SECRET is missing in production/strict auth mode.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service configuration error.",
            )
        # Development mode without secret is not permitted to decode forged tokens
        logger.warning("Rejecting unverified token: SUPABASE_JWT_SECRET not configured.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: JWT secret not configured.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Inspect unverified header to ensure algorithm matches configuration
        unverified_header = jwt.get_unverified_header(token)
        alg = unverified_header.get("alg")
        if not alg or alg.lower() == "none":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unsigned tokens are strictly rejected.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        expected_alg = settings.SUPABASE_JWT_ALGORITHM or "HS256"
        if alg != expected_alg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token signing algorithm: expected '{expected_alg}'.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        decode_options = {
            "verify_signature": True,
            "require": ["exp", "sub"],
        }
        if settings.SUPABASE_JWT_AUDIENCE:
            decode_options["verify_aud"] = True
            payload = jwt.decode(
                token,
                secret,
                algorithms=[expected_alg],
                audience=settings.SUPABASE_JWT_AUDIENCE,
                options=decode_options,
            )
        else:
            decode_options["verify_aud"] = False
            payload = jwt.decode(
                token,
                secret,
                algorithms=[expected_alg],
                options=decode_options,
            )

        user_id = payload.get("sub") or payload.get("id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is missing required subject claim.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        email = payload.get("email")
        role, org_id = derive_trusted_role_and_org(payload)

        return AuthenticatedUser(
            user_id=str(user_id),
            email=email,
            role=role,
            org_id=org_id,
            is_authenticated=True,
            is_demo=False,
        )

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token signature.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException:
        raise
    except Exception as err:
        logger.error(f"Unexpected token verification failure: {err}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication verification failed.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    x_stockwise_role: Optional[str] = Header(None, alias="X-StockWise-Role"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
) -> AuthenticatedUser:
    """
    Primary dependency for authenticating requests.
    - Production: Validates cryptographic Supabase Bearer token; rejects demo tokens and client headers.
    - Development: Permits demo tokens or explicit persona headers ONLY when ALLOW_DEMO_AUTH is active.
    - Fail-closed: Never defaults unauthenticated requests to admin in production.
    """
    is_prod = settings.is_production()
    demo_allowed = settings.is_demo_allowed()

    # 1. Bearer token provided
    if credentials and credentials.credentials:
        token = credentials.credentials.strip()

        # Check for demo tokens
        if token.startswith("demo-"):
            if not demo_allowed:
                logger.warning("Rejected demo token in production or strict environment.")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Demo tokens are rejected in production mode.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            demo_role = token.replace("demo-", "").replace("-token", "").lower()
            if demo_role in DEMO_PERSONAS:
                return DEMO_PERSONAS[demo_role]

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Unknown demo persona '{demo_role}'.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Production / Real JWT verification
        return verify_supabase_jwt(token)

    # 2. Strict enforcement check in production or when REQUIRE_AUTH is true
    if settings.REQUIRE_AUTH or is_prod or not demo_allowed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Development / Test Fallback (Explicitly allowed only in non-production)
    if demo_allowed:
        if x_stockwise_role and x_stockwise_role.lower() in DEMO_PERSONAS:
            persona = DEMO_PERSONAS[x_stockwise_role.lower()]
            if x_user_id:
                return AuthenticatedUser(
                    user_id=x_user_id,
                    email=persona.email,
                    role=persona.role,
                    org_id=persona.org_id,
                    is_authenticated=True,
                    is_demo=True,
                )
            return persona

        # Default development persona: admin with full system access (ONLY in local development)
        return DEMO_PERSONAS["admin"]

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_roles(allowed_roles: List[str]):
    """
    Dependency factory enforcing server-side Role-Based Access Control (RBAC).
    Admins are always authorized across all portals.
    """
    def role_checker(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if user.role == "admin":
            return user

        if user.role not in allowed_roles:
            logger.warning(
                f"Unauthorized role access attempt: user={user.user_id}, "
                f"role={user.role}, required={allowed_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Insufficient privileges. Required role: {', '.join(allowed_roles)} (current: '{user.role}')",
            )
        return user

    return role_checker


def enforce_tenant_isolation(user: AuthenticatedUser, resource_org_id: Optional[str], resource_name: str = "Resource") -> None:
    """
    Validates that a non-admin user cannot access or mutate resources belonging to another organization.
    Returns 404 (or 403) to prevent tenant enumeration and information disclosure.
    """
    if user.role == "admin":
        return

    if not user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Authenticated user has no assigned organization context.",
        )

    if resource_org_id and resource_org_id != user.org_id:
        logger.warning(
            f"Tenant isolation breach blocked: user={user.user_id} (org={user.org_id}) "
            f"attempted to access {resource_name} of org={resource_org_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_name} not found.",
        )


# Convenient FastAPI dependency shorthands
RequireAdmin = Depends(require_roles(["admin"]))
RequirePlanner = Depends(require_roles(["admin", "planner"]))
RequireLogistics = Depends(require_roles(["admin", "logistics"]))
RequireDistributor = Depends(require_roles(["admin", "distributor"]))
RequireRetailer = Depends(require_roles(["admin", "retailer"]))
RequireAuthenticated = Depends(require_roles(["admin", "planner", "logistics", "viewer"]))
