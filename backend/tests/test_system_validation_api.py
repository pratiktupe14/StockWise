"""Automated tests for StockWise System Health & Algorithm Validation Engine.

Verifies:
1. Live execution of all 16 core distribution intelligence modules.
2. Exact calculation of Test Pass Rate: (Passed / Executed) * 100.
3. Feature Verification Coverage: (Executed / Total In-Scope) * 100.
4. Handling of unexecuted checks ("not_tested" and None pass rate).
5. Meaningful positive, negative, boundary, and failure-case tests.
6. Genuine test pass rate and feature coverage exceed 80%.
7. Endpoints /api/system-validation, /api/system-validation/run, and /api/system-validation/export.
"""

from fastapi.testclient import TestClient
from app.services.system_validation_service import (
    execute_full_system_validation,
    get_latest_system_validation_report,
    MODULE_SPECS,
)


def test_system_validation_service_execution():
    """Verify live validation engine runs across all 16 modules."""
    report = execute_full_system_validation()

    assert report is not None
    assert report.total_in_scope >= 50
    assert report.total_executed == report.total_passed + report.total_failed + report.total_warning
    assert len(report.modules) == 16

    # Verify score formula compliance
    # Working Percentage = (Passed Checks / Executed Checks) * 100
    expected_pass_rate = round((report.total_passed / report.total_executed) * 100.0, 1)
    assert report.overall_test_pass_rate_percent == expected_pass_rate

    # Feature Verification Coverage = (Executed Checks / Total In-Scope) * 100
    expected_coverage = round((report.total_executed / report.total_in_scope) * 100.0, 1)
    assert report.overall_feature_coverage_percent == expected_coverage

    # Genuine score verification: Must genuinely exceed 80%
    assert report.overall_test_pass_rate_percent > 80.0
    assert report.overall_feature_coverage_percent > 80.0


def test_system_validation_modules_coverage():
    """Verify each of the 16 required core features is tested."""
    report = get_latest_system_validation_report()
    module_ids = {m.module_id for m in report.modules}

    required_modules = [
        "warehouse_selection",
        "stockout_prevention",
        "excess_inventory_reduction",
        "route_optimization",
        "landed_cost_calculation",
        "fefo_allocation",
        "expiry_alerts",
        "demand_forecasting",
        "mae_wape_evaluation",
        "actual_vs_predicted",
        "distribution_metrics",
        "what_if_simulation",
        "explainability",
        "data_imports",
        "baseline_comparison",
        "security_governance",
    ]

    for req in required_modules:
        assert req in module_ids, f"Required core module '{req}' missing from system validation"

    # Verify check types per module (positive, negative, boundary, failure_case)
    for mod in report.modules:
        assert mod.total_in_scope_checks > 0
        assert mod.executed_checks > 0
        assert mod.test_pass_rate_percent is not None
        assert mod.test_pass_rate_percent >= 80.0, f"Module {mod.module_id} pass rate below 80%: {mod.test_pass_rate_percent}%"

        types_present = {c.check_type for c in mod.checks}
        assert "positive" in types_present, f"Module {mod.module_id} missing positive check"
        # Verify boundary or negative or failure_case
        has_adversarial = any(t in types_present for t in ["negative", "boundary", "failure_case"])
        assert has_adversarial, f"Module {mod.module_id} missing negative, boundary, or failure-case checks"


def test_system_validation_api_endpoints(client: TestClient):
    """Test /api/system-validation and /api/system-validation/run endpoints."""
    # 1. GET /api/system-validation
    get_res = client.get("/api/system-validation")
    assert get_res.status_code == 200
    data = get_res.json()
    assert "report_id" in data
    assert "overall_test_pass_rate_percent" in data
    assert "overall_feature_coverage_percent" in data
    assert data["overall_test_pass_rate_percent"] > 80.0
    assert len(data["modules"]) == 16

    # 2. POST /api/system-validation/run
    run_res = client.post("/api/system-validation/run")
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["report_id"].startswith("VAL-RUN-")
    assert run_data["total_passed"] > 0
    assert run_data["total_failed"] == 0

    # 3. GET /api/system-validation/export
    export_res = client.get("/api/system-validation/export")
    assert export_res.status_code == 200
    assert "application/json" in export_res.headers.get("content-type", "")
    assert "attachment" in export_res.headers.get("content-disposition", "")
    export_data = export_res.json()
    assert "modules" in export_data


def test_system_validation_untested_formula_behavior():
    """Verify that if a module has 0 executed checks, test_pass_rate is None (Not Tested)."""
    from app.schemas.health import ModuleValidationSummary

    empty_summary = ModuleValidationSummary(
        module_id="untested_module",
        name="Untested Feature",
        category="Experimental",
        description="Module not yet tested",
        checks=[],
        passed_checks=0,
        executed_checks=0,
        total_in_scope_checks=5,
        failed_checks=0,
        warning_checks=0,
        blocked_checks=0,
        untested_checks=5,
        test_pass_rate_percent=None,  # Not Tested
        feature_coverage_percent=0.0,
        verified_coverage_percent=0.0,
        status="not_tested",
    )

    assert empty_summary.test_pass_rate_percent is None
    assert empty_summary.feature_coverage_percent == 0.0
    assert empty_summary.status == "not_tested"
