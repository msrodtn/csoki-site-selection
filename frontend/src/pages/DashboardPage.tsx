import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Radar,
  MapPin,
  TrendingUp,
  CheckCircle2,
  Clock,
  ArrowRight,
  FileText,
} from 'lucide-react';
import { useScoutStats, useScoutJobs, useScoutReports } from '../hooks/useScout';
import type { ScoutReportStatus } from '../types/store';

function StatCard({ label, value, icon: Icon, suffix, loading }: {
  label: string;
  value: number;
  icon: React.ElementType;
  suffix?: string;
  loading?: boolean;
}) {
  const [displayed, setDisplayed] = useState(0);

  useEffect(() => {
    if (loading) return;
    const duration = 600;
    const steps = 30;
    const increment = value / steps;
    let current = 0;
    const timer = setInterval(() => {
      current += increment;
      if (current >= value) {
        setDisplayed(value);
        clearInterval(timer);
      } else {
        setDisplayed(Math.round(current));
      }
    }, duration / steps);
    return () => clearInterval(timer);
  }, [value, loading]);

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-9 h-9 rounded-lg bg-gray-50 flex items-center justify-center">
          <Icon className="w-4.5 h-4.5 text-gray-500" />
        </div>
        <span className="text-sm text-gray-500">{label}</span>
      </div>
      {loading ? (
        <div className="h-9 w-16 bg-gray-100 rounded animate-pulse" />
      ) : (
        <p className="text-3xl font-semibold text-gray-900">
          {displayed}{suffix}
        </p>
      )}
    </div>
  );
}

function statusBadge(status: ScoutReportStatus) {
  const styles: Record<string, string> = {
    pending: 'bg-amber-50 text-amber-700 border-amber-200',
    approved: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    rejected: 'bg-red-50 text-red-700 border-red-200',
    flagged: 'bg-orange-50 text-orange-700 border-orange-200',
  };
  const labels: Record<string, string> = {
    pending: 'Pending Review',
    approved: 'Approved',
    rejected: 'Rejected',
    flagged: 'Flagged',
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${styles[status] || styles.pending}`}>
      {labels[status] || 'Pending Review'}
    </span>
  );
}

const MARKET_NAMES: Record<string, string> = {
  IA: 'Iowa',
  NE: 'Nebraska',
  NV: 'Nevada',
  ID: 'Idaho',
};

export function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useScoutStats();
  const { data: jobs } = useScoutJobs();
  const { data: reports } = useScoutReports();

  const activeJobs = jobs?.filter((j) => j.status === 'pending' || j.status === 'in_progress') || [];
  const recentReports = reports?.slice(0, 5) || [];

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">Overview of your site selection pipeline</p>
        </div>

        {/* Stat Cards */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          <StatCard
            label="Sites Analyzed"
            value={stats?.total_reports ?? 0}
            icon={MapPin}
            loading={statsLoading}
          />
          <StatCard
            label="Active Jobs"
            value={stats?.active_jobs ?? 0}
            icon={Radar}
            loading={statsLoading}
          />
          <StatCard
            label="Avg Confidence"
            value={stats?.avg_confidence ?? 0}
            icon={TrendingUp}
            suffix="%"
            loading={statsLoading}
          />
          <StatCard
            label="Approval Rate"
            value={stats?.approval_rate ?? 0}
            icon={CheckCircle2}
            suffix="%"
            loading={statsLoading}
          />
        </div>

        {/* Active Jobs */}
        {activeJobs.length > 0 && (
          <div className="mb-8">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-gray-900">Active Jobs</h2>
              <Link to="/scout/deploy" className="text-sm text-red-600 hover:text-red-700 font-medium flex items-center gap-1">
                Deploy New <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
            <div className="space-y-3">
              {activeJobs.map((job) => (
                <div key={job.id} className="bg-white rounded-xl border border-gray-200 p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Radar className="w-4 h-4 text-red-500 animate-pulse" />
                      <span className="font-medium text-gray-900 text-sm">
                        {MARKET_NAMES[job.market] || job.market}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 text-xs text-gray-500">
                      <Clock className="w-3.5 h-3.5" />
                      {Math.round(job.progress)}% complete
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex-1 bg-gray-100 rounded-full h-2">
                      <div
                        className="bg-red-500 h-2 rounded-full transition-all duration-500"
                        style={{ width: `${job.progress}%` }}
                      />
                    </div>
                    <span className="text-xs font-medium text-gray-600 tabular-nums">
                      {job.sites_completed}/{job.sites_total} sites
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recent Reports */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-gray-900">Recent Reports</h2>
            <Link to="/scout/reports" className="text-sm text-red-600 hover:text-red-700 font-medium flex items-center gap-1">
              View All <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Address</th>
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Market</th>
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Confidence</th>
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Status</th>
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {recentReports.map((report) => (
                  <tr key={report.id} className="border-b border-gray-50 last:border-0 hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3">
                      <span className="text-sm font-medium text-gray-900">{report.site_address}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm text-gray-600">{report.market}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-16 bg-gray-100 rounded-full h-1.5">
                          <div
                            className={`h-1.5 rounded-full ${
                              (report.confidence_score ?? 0) >= 80 ? 'bg-emerald-500' :
                              (report.confidence_score ?? 0) >= 60 ? 'bg-amber-500' : 'bg-red-500'
                            }`}
                            style={{ width: `${report.confidence_score ?? 0}%` }}
                          />
                        </div>
                        <span className="text-sm font-medium text-gray-700 tabular-nums">{report.confidence_score ?? 0}%</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {statusBadge(report.decision_status)}
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        to={`/scout/reports/${report.id}`}
                        className="text-sm text-gray-400 hover:text-gray-600"
                      >
                        <FileText className="w-4 h-4" />
                      </Link>
                    </td>
                  </tr>
                ))}
                {recentReports.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-400">
                      No reports yet. Deploy a SCOUT analysis to get started.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
