import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Search, ArrowUpDown, FileText, X, AlertTriangle } from 'lucide-react';
import { useScoutReports } from '../../hooks/useScout';
import type { ScoutReport, ScoutReportStatus } from '../../types/store';

const DEMO_BANNER_KEY = 'csoki-reports-demo-dismissed';

function confidenceColor(score: number) {
  if (score >= 80) return 'bg-emerald-500';
  if (score >= 60) return 'bg-amber-500';
  return 'bg-red-500';
}

function statusBadge(status: ScoutReportStatus) {
  const styles: Record<string, string> = {
    pending: 'bg-amber-50 text-amber-700 border-amber-200',
    approved: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    rejected: 'bg-red-50 text-red-700 border-red-200',
    flagged: 'bg-orange-50 text-orange-700 border-orange-200',
  };
  const labels: Record<string, string> = {
    pending: 'Pending',
    approved: 'Approved',
    rejected: 'Rejected',
    flagged: 'Flagged',
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${styles[status] || styles.pending}`}>
      {labels[status] || 'Pending'}
    </span>
  );
}

function agentBar(score: number | null) {
  const s = score ?? 0;
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-12 bg-gray-100 rounded-full h-1">
        <div
          className={`h-1 rounded-full ${s >= 8 ? 'bg-emerald-500' : s >= 6 ? 'bg-amber-500' : 'bg-red-500'}`}
          style={{ width: `${s * 10}%` }}
        />
      </div>
      <span className="text-xs tabular-nums text-gray-500 w-6">{s.toFixed(1)}</span>
    </div>
  );
}

export function ReportsPage() {
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<'confidence' | 'date'>('confidence');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [demoDismissed, setDemoDismissed] = useState(() => {
    try { return localStorage.getItem(DEMO_BANNER_KEY) === 'true'; } catch { return false; }
  });

  const { data: reports, isLoading, isError, error } = useScoutReports();

  const dismissDemo = () => {
    setDemoDismissed(true);
    try { localStorage.setItem(DEMO_BANNER_KEY, 'true'); } catch { /* ignore */ }
  };

  const filtered = (reports || [])
    .filter((r: ScoutReport) => {
      if (filterStatus !== 'all' && r.decision_status !== filterStatus) return false;
      if (search && !r.site_address.toLowerCase().includes(search.toLowerCase()) &&
          !(r.market || '').toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    })
    .sort((a: ScoutReport, b: ScoutReport) => {
      if (sortBy === 'confidence') return (b.confidence_score ?? 0) - (a.confidence_score ?? 0);
      return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime();
    });

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">Reports</h1>
            <p className="text-sm text-gray-500 mt-1">{reports?.length ?? 0} site analyses</p>
          </div>
        </div>

        {/* Demo data banner */}
        {!demoDismissed && (
          <div className="flex items-center gap-3 p-3 mb-6 bg-amber-50 border border-amber-200 rounded-lg">
            <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0" />
            <p className="text-sm text-amber-700 flex-1">
              <strong>Demo Data</strong> — These reports are sample data for demonstration. Real analysis reports will appear here once SCOUT agents are deployed on the Mac Mini.
            </p>
            <button onClick={dismissDemo} className="text-amber-400 hover:text-amber-600 flex-shrink-0">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Filters */}
        <div className="flex items-center gap-3 mb-6">
          <div className="relative flex-1 max-w-sm">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search by address or market..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-white border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-red-500/20 focus:border-red-500"
            />
          </div>
          <div className="flex items-center gap-1 bg-white border border-gray-200 rounded-lg p-0.5">
            {['all', 'pending', 'approved', 'rejected'].map((status) => (
              <button
                key={status}
                onClick={() => setFilterStatus(status)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  filterStatus === status
                    ? 'bg-gray-900 text-white'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {status.charAt(0).toUpperCase() + status.slice(1)}
              </button>
            ))}
          </div>
          <button
            onClick={() => setSortBy(sortBy === 'confidence' ? 'date' : 'confidence')}
            className="flex items-center gap-1.5 px-3 py-2 bg-white border border-gray-200 rounded-lg text-xs text-gray-600 hover:text-gray-900 transition-colors"
          >
            <ArrowUpDown className="w-3.5 h-3.5" />
            {sortBy === 'confidence' ? 'By Score' : 'By Date'}
          </button>
        </div>

        {/* Reports table */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          {isLoading ? (
            <div className="p-8 text-center text-sm text-gray-400">Loading reports...</div>
          ) : isError ? (
            <div className="p-8 text-center">
              <AlertTriangle className="w-8 h-8 text-amber-400 mx-auto mb-2" />
              <p className="text-sm text-gray-600 font-medium">Unable to load reports</p>
              <p className="text-xs text-gray-400 mt-1">
                {error instanceof Error ? error.message : 'The SCOUT backend may not be running yet.'}
              </p>
            </div>
          ) : (
            <>
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-100">
                    <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Site</th>
                    <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Score</th>
                    <th className="text-left text-xs font-medium text-gray-500 px-4 py-3 hidden xl:table-cell">Feas</th>
                    <th className="text-left text-xs font-medium text-gray-500 px-4 py-3 hidden xl:table-cell">Reg</th>
                    <th className="text-left text-xs font-medium text-gray-500 px-4 py-3 hidden xl:table-cell">Grow</th>
                    <th className="text-left text-xs font-medium text-gray-500 px-4 py-3 hidden xl:table-cell">Sent</th>
                    <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Flags</th>
                    <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Status</th>
                    <th className="text-left text-xs font-medium text-gray-500 px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((report: ScoutReport) => (
                    <tr key={report.id} className="border-b border-gray-50 last:border-0 hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3">
                        <div>
                          <span className="text-sm font-medium text-gray-900">{report.site_address}</span>
                          <p className="text-xs text-gray-400">{report.market}</p>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-16 bg-gray-100 rounded-full h-2">
                            <div
                              className={`h-2 rounded-full ${confidenceColor(report.confidence_score ?? 0)}`}
                              style={{ width: `${report.confidence_score ?? 0}%` }}
                            />
                          </div>
                          <span className="text-sm font-semibold text-gray-700 tabular-nums w-10">{report.confidence_score ?? 0}%</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 hidden xl:table-cell">{agentBar(report.feasibility_score)}</td>
                      <td className="px-4 py-3 hidden xl:table-cell">{agentBar(report.regulatory_score)}</td>
                      <td className="px-4 py-3 hidden xl:table-cell">{agentBar(report.growth_score)}</td>
                      <td className="px-4 py-3 hidden xl:table-cell">{agentBar(report.sentiment_score)}</td>
                      <td className="px-4 py-3">
                        {(report.flags?.length ?? 0) > 0 ? (
                          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-orange-50 text-orange-600">
                            {report.flags!.length}
                          </span>
                        ) : (
                          <span className="text-xs text-gray-300">-</span>
                        )}
                      </td>
                      <td className="px-4 py-3">{statusBadge(report.decision_status)}</td>
                      <td className="px-4 py-3">
                        <Link
                          to={`/scout/reports/${report.id}`}
                          className="text-gray-400 hover:text-gray-600 transition-colors"
                        >
                          <FileText className="w-4 h-4" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filtered.length === 0 && (
                <div className="p-8 text-center text-sm text-gray-500">
                  No reports match your filters.
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
