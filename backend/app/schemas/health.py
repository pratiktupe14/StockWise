from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


class DatabaseHealth(BaseModel):
    connected: bool = Field(..., description="Whether database query succeeded")
    status: str = Field(..., description="'connected' or 'disconnected'")
    message: str = Field(..., description="Detailed status message or error summary")
    dialect: str = Field(..., description="Database dialect, e.g. postgresql")
    latency_ms: Optional[float] = Field(None, description="Round-trip check duration in milliseconds")


class SystemValidationCheck(BaseModel):
    check_id: str = Field(..., description="Unique test check identifier, e.g. wh-sel-pos-01")
    title: str = Field(..., description="Human-readable title describing the validation case")
    module_id: str = Field(..., description="Target module identifier, e.g. warehouse_selection")
    module_name: str = Field(..., description="Display name of the module")
    category: str = Field(..., description="Feature category: Optimization & Solver, Inventory & Expiry, etc.")
    check_type: Literal["positive", "negative", "boundary", "failure_case"] = Field(
        ..., description="Verification classification: positive, negative, boundary, or failure_case"
    )
    status: Literal["passed", "failed", "warning", "blocked", "untested"] = Field(
        ..., description="Result status: passed, failed, warning, blocked, or untested"
    )
    execution_time_ms: float = Field(..., description="Execution duration in milliseconds")
    message: str = Field(..., description="Summary explanation of the test outcome")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Concrete output data, formulas, and math assertions")
    error_detail: Optional[str] = Field(None, description="Detailed stack trace or error message if check failed")
    tested_at: Optional[str] = Field(None, description="ISO-8601 timestamp of check execution")


class ModuleValidationSummary(BaseModel):
    module_id: str = Field(..., description="Unique module slug")
    name: str = Field(..., description="Module display name")
    category: str = Field(..., description="Functional group")
    description: str = Field(..., description="Scope of algorithms and business rules tested")
    checks: List[SystemValidationCheck] = Field(default_factory=list, description="List of concrete check results")
    passed_checks: int = Field(0, description="Count of passed test checks")
    executed_checks: int = Field(0, description="Count of executed test checks (passed + failed + warning)")
    total_in_scope_checks: int = Field(0, description="Total required checks for full module verification")
    failed_checks: int = Field(0, description="Count of failing test checks")
    warning_checks: int = Field(0, description="Count of warning test checks")
    blocked_checks: int = Field(0, description="Count of blocked test checks")
    untested_checks: int = Field(0, description="Count of not-yet-executed checks")
    test_pass_rate_percent: Optional[float] = Field(
        None, description="Working Percentage = (Passed / Executed) * 100. None if no checks executed."
    )
    feature_coverage_percent: float = Field(
        0.0, description="Feature Verification Coverage = (Executed / Total In-Scope) * 100"
    )
    verified_coverage_percent: float = Field(
        0.0, description="Verified Feature Coverage = (Passed / Total In-Scope) * 100"
    )
    status: str = Field("passing", description="'passing', 'degraded', 'failing', or 'not_tested'")


class SystemValidationReport(BaseModel):
    report_id: str = Field(..., description="Unique run UUID")
    evaluated_at: str = Field(..., description="UTC ISO-8601 timestamp of evaluation")
    overall_test_pass_rate_percent: Optional[float] = Field(
        None, description="Overall Executed Pass Rate = (Total Passed / Total Executed) * 100"
    )
    overall_feature_coverage_percent: float = Field(
        0.0, description="Overall In-Scope Coverage = (Total Executed / Total In-Scope) * 100"
    )
    overall_verified_coverage_percent: float = Field(
        0.0, description="Overall Verified Coverage = (Total Passed / Total In-Scope) * 100"
    )
    total_passed: int = Field(0, description="Total passed checks across all modules")
    total_failed: int = Field(0, description="Total failed checks across all modules")
    total_warning: int = Field(0, description="Total warning checks across all modules")
    total_blocked: int = Field(0, description="Total blocked checks across all modules")
    total_untested: int = Field(0, description="Total untested checks across all modules")
    total_executed: int = Field(0, description="Total executed checks")
    total_in_scope: int = Field(0, description="Total planned checks across all modules")
    modules: List[ModuleValidationSummary] = Field(default_factory=list, description="Per-module breakdown")
    last_validation_timestamp: str = Field(..., description="Human-readable timestamp of the last run")


class HealthResponse(BaseModel):
    status: str = Field(..., description="'healthy' when all systems operational, 'degraded' when DB offline")
    app_name: str = Field("StockWise", description="Application name")
    tagline: str = Field("The right stock. At the right place. Before it is too late.", description="Application tagline")
    version: str = Field("0.1.0", description="Backend service version")
    environment: str = Field(..., description="Runtime environment: development, staging, production")
    timestamp: str = Field(..., description="UTC ISO-8601 timestamp of health evaluation")
    api: str = Field("online", description="API server availability state")
    database: DatabaseHealth = Field(..., description="Live database connectivity assessment")
    validation_summary: Optional[SystemValidationReport] = Field(
        None, description="Latest algorithm validation and test pass rate report"
    )
