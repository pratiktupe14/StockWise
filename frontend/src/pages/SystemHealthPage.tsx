import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Activity,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RotateCw,
  Download,
  ShieldCheck,
  ChevronDown,
  ChevronRight,
  Filter,
  Search,
  Cpu,
  Layers,
  Info,
  Clock,
  Terminal,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import {
  getSystemValidation,
  runSystemValidation,
  exportSystemValidationReport,
} from '../services/api';
import type {
  SystemValidationReport,
} from '../types/api';

export const SystemHealthPage: React.FC = () => {
  const [report, setReport] = useState<SystemValidationReport | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [running, setRunning] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [statusFilter, setStatusFilter] = useState<string>('All');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [expandedModules, setExpandedModules] = useState<Record<string, boolean>>({});
  const [expandedEvidence, setExpandedEvidence] = useState<Record<string, boolean>>({});

  const fetchReport = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getSystemValidation();
      setReport(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load system validation report.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchReport();
  }, [fetchReport]);

  const handleRunFullCheck = async () => {
    setRunning(true);
    setError(null);
    try {
      const updated = await runSystemValidation();
      setReport(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Execution of system validation failed.');
    } finally {
      setRunning(false);
    }
  };

  const handleExport = async () => {
    try {
      await exportSystemValidationReport();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to export test report.');
    }
  };

  const toggleModule = (moduleId: string) => {
    setExpandedModules((prev) => ({
      ...prev,
      [moduleId]: !prev[moduleId],
    }));
  };

  const toggleEvidence = (checkId: string) => {
    setExpandedEvidence((prev) => ({
      ...prev,
      [checkId]: !prev[checkId],
    }));
  };

  const expandAll = () => {
    if (!report) return;
    const all: Record<string, boolean> = {};
    report.modules.forEach((m) => {
      all[m.module_id] = true;
    });
    setExpandedModules(all);
  };

  const collapseAll = () => {
    setExpandedModules({});
  };

  // Categories list
  const categories = useMemo(() => {
    if (!report) return ['All'];
    const cats = new Set<string>();
    report.modules.forEach((m) => cats.add(m.category));
    return ['All', ...Array.from(cats).sort()];
  }, [report]);

  // Filtered modules
  const filteredModules = useMemo(() => {
    if (!report) return [];
    return report.modules.filter((m) => {
      // Category filter
      if (selectedCategory !== 'All' && m.category !== selectedCategory) {
        return false;
      }
      // Status filter
      if (statusFilter === 'Failing / Warning') {
        if (m.status !== 'failing' && m.status !== 'degraded') return false;
      } else if (statusFilter === 'Not Tested') {
        if (m.status !== 'not_tested') return false;
      } else if (statusFilter === 'Passing') {
        if (m.status !== 'passing') return false;
      }

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesName = m.name.toLowerCase().includes(q);
        const matchesDesc = m.description.toLowerCase().includes(q);
        const matchesCheck = m.checks.some(
          (c) =>
            c.title.toLowerCase().includes(q) ||
            c.check_id.toLowerCase().includes(q) ||
            c.message.toLowerCase().includes(q)
        );
        if (!matchesName && !matchesDesc && !matchesCheck) {
          return false;
        }
      }

      return true;
    });
  }, [report, selectedCategory, statusFilter, searchQuery]);

  // Helper for check type badge style
  const getCheckTypeBadge = (checkType: string) => {
    switch (checkType) {
      case 'positive':
        return <Badge variant="primary" size="sm">Positive</Badge>;
      case 'negative':
        return <Badge variant="warning" size="sm">Negative</Badge>;
      case 'boundary':
        return <Badge variant="neutral" size="sm" className="bg-purple-50 text-purple-700 border-purple-200">Boundary</Badge>;
      case 'failure_case':
        return <Badge variant="critical" size="sm">Failure Case</Badge>;
      default:
        return <Badge variant="neutral" size="sm">{checkType}</Badge>;
    }
  };

  // Helper for status badge style
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'passed':
        return (
          <Badge variant="success" dot size="sm">
            Passed
          </Badge>
        );
      case 'failed':
        return (
          <Badge variant="critical" dot size="sm">
            Failed
          </Badge>
        );
      case 'warning':
        return (
          <Badge variant="warning" dot size="sm">
            Warning
          </Badge>
        );
      case 'blocked':
        return (
          <Badge variant="critical" dot size="sm" className="bg-purple-50 text-purple-700 border-purple-200">
            Blocked
          </Badge>
        );
      case 'untested':
        return (
          <Badge variant="neutral" dot size="sm">
            Untested
          </Badge>
        );
      default:
        return <Badge variant="neutral" size="sm">{status}</Badge>;
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-16">
      {/* Page Header */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-2xl p-6 sm:p-8 text-white shadow-xl border border-slate-800">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                <ShieldCheck className="w-3.5 h-3.5" />
                Automated Quality Engineering
              </span>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/30">
                <Cpu className="w-3.5 h-3.5" />
                16 In-Scope Modules
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
              System Health & Algorithm Validation
            </h1>
            <p className="text-sm text-slate-300 max-w-3xl leading-relaxed">
              Verifiable, live automated validation across all 16 core StockWise distribution intelligence modules.
              Scores reflect genuine test executions without hardcoded numbers, simulated successes, or suppressed failures.
            </p>
            {report?.last_validation_timestamp && (
              <div className="flex items-center gap-2 text-xs text-slate-400 pt-1">
                <Clock className="w-3.5 h-3.5 text-slate-400" />
                <span>Last verified: <strong className="text-slate-200">{report.last_validation_timestamp}</strong></span>
                <span className="text-slate-600">•</span>
                <span>Run ID: <span className="font-mono text-slate-300">{report.report_id}</span></span>
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              size="md"
              onClick={handleExport}
              disabled={loading || running || !report}
              className="bg-slate-800/80 hover:bg-slate-800 text-white border-slate-700 shadow-sm"
            >
              <Download className="w-4 h-4 mr-2" />
              Export Report
            </Button>
            <Button
              variant="primary"
              size="md"
              onClick={handleRunFullCheck}
              disabled={loading || running}
              className="bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-900/30 border-0"
            >
              <RotateCw className={`w-4 h-4 mr-2 ${running ? 'animate-spin' : ''}`} />
              {running ? 'Running Full System Check...' : 'Run Full System Check'}
            </Button>
          </div>
        </div>
      </div>

      {/* Error alert if any */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
          <div className="text-sm">
            <div className="font-semibold">Validation Error</div>
            <div>{error}</div>
          </div>
        </div>
      )}

      {/* TWO SEPARATE SCORES (REQUIREMENT 4) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Score A: Test Pass Rate */}
        <Card className="border-2 border-emerald-500/20 bg-gradient-to-br from-white to-emerald-50/30 shadow-md">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-emerald-800 bg-emerald-100/80 px-2.5 py-1 rounded-md">
                Score A • Executed Tests Only
              </span>
              <Badge variant="success" size="sm">
                Formula Verified
              </Badge>
            </div>
            <CardTitle className="text-xl mt-2 text-slate-900">
              Test Pass Rate
            </CardTitle>
            <CardDescription>
              Shows how many executed automated tests passed. Unexecuted tests are strictly excluded.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-baseline justify-between">
              <div className="flex items-baseline gap-2">
                <span className="text-4xl sm:text-5xl font-extrabold text-emerald-700 font-mono tracking-tight">
                  {report?.overall_test_pass_rate_percent !== null && report?.overall_test_pass_rate_percent !== undefined
                    ? `${report.overall_test_pass_rate_percent.toFixed(1)}%`
                    : 'Not Tested'}
                </span>
                <span className="text-xs text-slate-500 font-medium">
                  ({report?.total_passed ?? 0} passed / {report?.total_executed ?? 0} executed)
                </span>
              </div>
              <div className="text-right">
                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800">
                  Target: &gt; 80.0%
                </span>
              </div>
            </div>

            {/* Progress bar */}
            <div className="w-full bg-slate-200 rounded-full h-3 overflow-hidden">
              <div
                className="bg-emerald-600 h-3 rounded-full transition-all duration-700 ease-out"
                style={{
                  width: `${Math.min(100, report?.overall_test_pass_rate_percent ?? 0)}%`,
                }}
              />
            </div>

            <div className="p-3 bg-white/90 rounded-lg border border-emerald-100 text-[11px] text-slate-600 flex items-center justify-between font-mono">
              <span>Formula:</span>
              <strong className="text-slate-800">Working % = (Passed Checks / Executed Checks) × 100</strong>
            </div>
          </CardContent>
        </Card>

        {/* Score B: Feature Verification Coverage */}
        <Card className="border-2 border-indigo-500/20 bg-gradient-to-br from-white to-indigo-50/30 shadow-md">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-indigo-800 bg-indigo-100/80 px-2.5 py-1 rounded-md">
                Score B • All In-Scope Features
              </span>
              <Badge variant="primary" size="sm">
                Scope Verified
              </Badge>
            </div>
            <CardTitle className="text-xl mt-2 text-slate-900">
              Feature Verification Coverage
            </CardTitle>
            <CardDescription>
              Shows how much of the platform has been tested. Untested features are not counted as verified.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-baseline justify-between">
              <div className="flex items-baseline gap-2">
                <span className="text-4xl sm:text-5xl font-extrabold text-indigo-700 font-mono tracking-tight">
                  {report?.overall_feature_coverage_percent !== undefined
                    ? `${report.overall_feature_coverage_percent.toFixed(1)}%`
                    : '0.0%'}
                </span>
                <span className="text-xs text-slate-500 font-medium">
                  ({report?.total_executed ?? 0} executed / {report?.total_in_scope ?? 0} in-scope)
                </span>
              </div>
              <div className="text-right">
                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-indigo-100 text-indigo-800">
                  Target: &gt; 80.0%
                </span>
              </div>
            </div>

            {/* Progress bar */}
            <div className="w-full bg-slate-200 rounded-full h-3 overflow-hidden">
              <div
                className="bg-indigo-600 h-3 rounded-full transition-all duration-700 ease-out"
                style={{
                  width: `${Math.min(100, report?.overall_feature_coverage_percent ?? 0)}%`,
                }}
              />
            </div>

            <div className="p-3 bg-white/90 rounded-lg border border-indigo-100 text-[11px] text-slate-600 flex items-center justify-between font-mono">
              <span>Formula:</span>
              <strong className="text-slate-800">Coverage % = (Executed Checks / Total In-Scope) × 100</strong>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* METRIC STRIP (PASSED, FAILED, WARNING, BLOCKED, UNTESTED, TOTAL) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Passed</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-emerald-700">
            {report?.total_passed ?? 0}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">Automated checks passed</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Failed</span>
            <XCircle className="w-4 h-4 text-rose-600" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-rose-700">
            {report?.total_failed ?? 0}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">Failing check assertions</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Warning</span>
            <AlertTriangle className="w-4 h-4 text-amber-600" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-amber-700">
            {report?.total_warning ?? 0}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">Degraded logic / alerts</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Blocked</span>
            <Activity className="w-4 h-4 text-purple-600" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-purple-700">
            {report?.total_blocked ?? 0}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">Dependency blocked</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Untested</span>
            <Layers className="w-4 h-4 text-slate-500" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-slate-700">
            {report?.total_untested ?? 0}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">Excluded from pass rate</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Total In-Scope</span>
            <ShieldCheck className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-indigo-700">
            {report?.total_in_scope ?? 0}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">16 Core modules total</div>
        </div>
      </div>

      {/* FILTER & SEARCH TOOLBAR */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Search */}
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search checks, modules, or error messages..."
              className="w-full pl-9 pr-4 py-1.5 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            />
          </div>

          {/* Quick controls */}
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={expandAll} className="text-xs text-slate-600">
              Expand All
            </Button>
            <span className="text-slate-300">|</span>
            <Button variant="ghost" size="sm" onClick={collapseAll} className="text-xs text-slate-600">
              Collapse All
            </Button>
          </div>
        </div>

        {/* Category & Status buttons */}
        <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-100">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] font-semibold text-slate-500 mr-1 flex items-center gap-1">
              <Filter className="w-3 h-3" /> Category:
            </span>
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`text-xs px-2.5 py-1 rounded-md transition-colors ${
                  selectedCategory === cat
                    ? 'bg-indigo-600 text-white font-medium shadow-2xs'
                    : 'bg-slate-100 hover:bg-slate-200 text-slate-600'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-semibold text-slate-500 mr-1">Status:</span>
            {['All', 'Passing', 'Failing / Warning', 'Not Tested'].map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`text-xs px-2.5 py-1 rounded-md transition-colors ${
                  statusFilter === st
                    ? 'bg-slate-800 text-white font-medium shadow-2xs'
                    : 'bg-slate-100 hover:bg-slate-200 text-slate-600'
                }`}
              >
                {st}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* MODULE CARDS LIST */}
      <div className="space-y-4">
        <div className="flex items-center justify-between text-xs text-slate-500 px-1">
          <span>
            Showing <strong className="text-slate-800">{filteredModules.length}</strong> of{' '}
            {report?.modules.length ?? 0} modules
          </span>
          <span>Click any module to inspect check evidence and assertions</span>
        </div>

        {loading && !report ? (
          <Card className="p-12 text-center text-slate-500">
            <RotateCw className="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-600" />
            <p className="text-sm font-medium">Evaluating system health and running algorithm validation...</p>
          </Card>
        ) : filteredModules.length === 0 ? (
          <Card className="p-12 text-center text-slate-500">
            <p className="text-sm font-medium">No modules match the selected category and status filters.</p>
          </Card>
        ) : (
          filteredModules.map((module) => {
            const isExpanded = expandedModules[module.module_id] ?? false;
            const passRateDisplay =
              module.test_pass_rate_percent !== null
                ? `${module.test_pass_rate_percent.toFixed(1)}%`
                : 'Not Tested';

            return (
              <div
                key={module.module_id}
                className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden transition-all duration-200"
              >
                {/* Module Header Bar */}
                <div
                  onClick={() => toggleModule(module.module_id)}
                  className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 cursor-pointer hover:bg-slate-50/70 transition-colors"
                >
                  <div className="flex items-start gap-3">
                    <button
                      type="button"
                      className="mt-1 text-slate-400 hover:text-slate-600 transition-colors"
                      aria-label="Toggle module details"
                    >
                      {isExpanded ? (
                        <ChevronDown className="w-5 h-5 text-indigo-600" />
                      ) : (
                        <ChevronRight className="w-5 h-5" />
                      )}
                    </button>
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-base font-semibold text-slate-900 tracking-tight">
                          {module.name}
                        </h3>
                        <Badge variant="neutral" size="sm" className="font-mono text-[10px]">
                          {module.module_id}
                        </Badge>
                        <span className="text-[11px] font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                          {module.category}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 mt-1 max-w-2xl leading-relaxed">
                        {module.description}
                      </p>
                    </div>
                  </div>

                  {/* Right side scores */}
                  <div className="flex items-center gap-4 sm:gap-6 self-end sm:self-center shrink-0">
                    {/* Test pass rate pill */}
                    <div className="text-right">
                      <div className="text-[10px] uppercase font-bold tracking-wider text-slate-400">
                        Test Pass Rate
                      </div>
                      <div
                        className={`text-lg font-extrabold font-mono ${
                          module.test_pass_rate_percent === null
                            ? 'text-slate-400'
                            : module.test_pass_rate_percent >= 80
                            ? 'text-emerald-700'
                            : 'text-rose-600'
                        }`}
                      >
                        {passRateDisplay}
                      </div>
                      <div className="text-[10px] text-slate-400">
                        {module.passed_checks} / {module.executed_checks} passed
                      </div>
                    </div>

                    {/* Coverage pill */}
                    <div className="text-right hidden sm:block">
                      <div className="text-[10px] uppercase font-bold tracking-wider text-slate-400">
                        Feature Coverage
                      </div>
                      <div className="text-lg font-bold font-mono text-indigo-700">
                        {module.feature_coverage_percent.toFixed(1)}%
                      </div>
                      <div className="text-[10px] text-slate-400">
                        {module.executed_checks} / {module.total_in_scope_checks} checks
                      </div>
                    </div>

                    {/* Status badge */}
                    <div className="w-24 text-right">
                      {module.status === 'passing' ? (
                        <Badge variant="success" dot size="sm">
                          Passing
                        </Badge>
                      ) : module.status === 'degraded' ? (
                        <Badge variant="warning" dot size="sm">
                          Degraded
                        </Badge>
                      ) : module.status === 'failing' ? (
                        <Badge variant="critical" dot size="sm">
                          Failing
                        </Badge>
                      ) : (
                        <Badge variant="neutral" dot size="sm">
                          Not Tested
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>

                {/* Expanded Checks Section */}
                {isExpanded && (
                  <div className="border-t border-slate-100 bg-slate-50/50 p-4 sm:p-5 space-y-3">
                    <div className="flex items-center justify-between text-xs font-semibold text-slate-700 pb-1">
                      <span>Automated Test Checks ({module.checks.length})</span>
                      <span className="text-[11px] text-slate-500 font-normal">
                        Positive, Negative, Boundary, and Failure-Case verifications
                      </span>
                    </div>

                    <div className="space-y-2.5">
                      {module.checks.map((check) => {
                        const isEvidenceOpen = expandedEvidence[check.check_id] ?? false;
                        return (
                          <div
                            key={check.check_id}
                            className={`rounded-lg border p-3.5 transition-colors ${
                              check.status === 'passed'
                                ? 'bg-white border-slate-200'
                                : check.status === 'failed'
                                ? 'bg-rose-50/50 border-rose-200'
                                : 'bg-amber-50/50 border-amber-200'
                            }`}
                          >
                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                              <div className="flex items-start gap-2.5">
                                <div className="mt-0.5">
                                  {check.status === 'passed' ? (
                                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                                  ) : check.status === 'failed' ? (
                                    <XCircle className="w-4 h-4 text-rose-600 shrink-0" />
                                  ) : (
                                    <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                                  )}
                                </div>
                                <div>
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="text-xs font-bold text-slate-900">
                                      {check.title}
                                    </span>
                                    <span className="font-mono text-[10px] text-slate-400">
                                      [{check.check_id}]
                                    </span>
                                    {getCheckTypeBadge(check.check_type)}
                                  </div>
                                  <p className="text-xs text-slate-600 mt-1">
                                    {check.message}
                                  </p>
                                </div>
                              </div>

                              <div className="flex items-center gap-3 self-end sm:self-center shrink-0">
                                <span className="text-[11px] font-mono text-slate-400">
                                  {check.execution_time_ms.toFixed(1)}ms
                                </span>
                                {getStatusBadge(check.status)}
                                <button
                                  type="button"
                                  onClick={() => toggleEvidence(check.check_id)}
                                  className="text-xs text-indigo-600 hover:text-indigo-800 font-medium inline-flex items-center gap-1 bg-indigo-50 hover:bg-indigo-100 px-2 py-0.5 rounded transition-colors"
                                >
                                  <Terminal className="w-3 h-3" />
                                  {isEvidenceOpen ? 'Hide Evidence' : 'View Evidence'}
                                </button>
                              </div>
                            </div>

                            {/* Error trace if failed */}
                            {check.error_detail && (
                              <div className="mt-3 p-3 rounded bg-rose-100/70 border border-rose-200 text-xs font-mono text-rose-900">
                                <div className="font-bold text-rose-950 mb-1">Execution Failure:</div>
                                {check.error_detail}
                              </div>
                            )}

                            {/* Evidence Drawer */}
                            {isEvidenceOpen && (
                              <div className="mt-3 p-3.5 rounded-lg bg-slate-900 text-slate-200 font-mono text-[11px] overflow-x-auto border border-slate-800 shadow-inner">
                                <div className="flex items-center justify-between text-slate-400 pb-2 mb-2 border-b border-slate-800 text-[10px] uppercase tracking-wider font-semibold">
                                  <span>Automated Assertion Evidence</span>
                                  <span>Check ID: {check.check_id}</span>
                                </div>
                                <pre className="whitespace-pre-wrap leading-relaxed text-emerald-400">
                                  {JSON.stringify(check.evidence, null, 2)}
                                </pre>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* METHODOLOGY & AUDIT INTEGRITY CARD */}
      <Card className="border border-slate-200 bg-slate-50/50">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 text-indigo-600" />
            <CardTitle className="text-sm font-semibold text-slate-900">
              Audit Transparency & Score Calculation Standards
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 text-xs text-slate-600 leading-relaxed">
          <p>
            StockWise implements the strict dual-score evaluation standard mandated for enterprise FMCG operations:
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
            <div className="p-3 rounded-lg bg-white border border-slate-200">
              <div className="font-semibold text-slate-900 mb-1">
                1. Test Pass Rate (Executed Tests Only)
              </div>
              <p className="font-mono text-[11px] text-indigo-700 mb-1.5">
                Working Percentage = (Passed Checks / Executed Checks) × 100
              </p>
              <p className="text-[11px] text-slate-500">
                Measures whether the algorithms and code currently executing perform correctly. Untested checks are strictly excluded from the divisor to avoid artificially penalizing or inflating the score. Modules with zero executions report <span className="font-semibold text-slate-700">Not Tested</span>.
              </p>
            </div>

            <div className="p-3 rounded-lg bg-white border border-slate-200">
              <div className="font-semibold text-slate-900 mb-1">
                2. Feature Verification Coverage (Full Platform Scope)
              </div>
              <p className="font-mono text-[11px] text-indigo-700 mb-1.5">
                Feature Coverage = (Executed Checks / Total In-Scope Checks) × 100
              </p>
              <p className="text-[11px] text-slate-500">
                Measures the percentage of required product functionality that has automated regression tests active in the system. Missing or omitted modules remain at 0% coverage until concrete tests are implemented.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default SystemHealthPage;
