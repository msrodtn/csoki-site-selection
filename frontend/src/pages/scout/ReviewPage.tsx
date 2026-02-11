import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  CheckCircle2,
  XCircle,
  Flag,
  FileText,
  Clock,
  ChevronDown,
} from 'lucide-react';
import { useScoutReports, useScoutDecisions, useSubmitDecision } from '../../hooks/useScout';
import type { ScoutReport, ScoutDecision } from '../../types/store';

const REJECTION_REASONS = [
  'Visibility/Access Issues',
  'Too Close to Competition',
  'Zoning Concerns',
  'Financial - Doesn\'t Pencil',
  'Negative Community Sentiment',
  'Data Quality Concerns',
  'Other',
];

function confidenceColor(score: number) {
  if (score >= 80) return 'bg-emerald-500';
  if (score >= 60) return 'bg-amber-500';
  return 'bg-red-500';
}

function PendingCard({ site, onDecision }: {
  site: ScoutReport;
  onDecision: (reportId: string, decision: 'approved' | 'rejected' | 'flagged', reason?: string) => void;
}) {
  const [showReject, setShowReject] = useState(false);
  const [reason, setReason] = useState('');

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">{site.site_address}</h3>
          <p className="text-xs text-gray-500">{site.market}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-16 bg-gray-100 rounded-full h-2">
            <div className={`h-2 rounded-full ${confidenceColor(site.confidence_score ?? 0)}`} style={{ width: `${site.confidence_score ?? 0}%` }} />
          </div>
          <span className="text-sm font-semibold text-gray-700 tabular-nums">{site.confidence_score ?? 0}%</span>
        </div>
      </div>

      {/* Agent scores row */}
      <div className="flex items-center gap-4 text-xs text-gray-500 mb-4">
        <span>Feas: <strong className="text-gray-700">{site.feasibility_score ?? '-'}</strong></span>
        <span>Reg: <strong className="text-gray-700">{site.regulatory_score ?? '-'}</strong></span>
        <span>Growth: <strong className="text-gray-700">{site.growth_score ?? '-'}</strong></span>
        <span className="ml-auto">
          {(site.strengths?.length ?? 0)} strengths &middot; {(site.flags?.length ?? 0)} flags
        </span>
      </div>

      {/* Decision buttons */}
      {!showReject ? (
        <div className="flex items-center gap-2">
          <button
            onClick={() => onDecision(site.id, 'approved')}
            className="flex items-center gap-1.5 px-3 py-2 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-700 transition-colors"
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            Approve
          </button>
          <button
            onClick={() => setShowReject(true)}
            className="flex items-center gap-1.5 px-3 py-2 border border-red-200 text-red-700 text-sm font-medium rounded-lg hover:bg-red-50 transition-colors"
          >
            <XCircle className="w-3.5 h-3.5" />
            Reject
          </button>
          <button
            onClick={() => onDecision(site.id, 'flagged')}
            className="flex items-center gap-1.5 px-3 py-2 border border-gray-200 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-50 transition-colors"
          >
            <Flag className="w-3.5 h-3.5" />
            Flag
          </button>
          <Link
            to={`/scout/reports/${site.id}`}
            className="ml-auto flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-600"
          >
            <FileText className="w-3.5 h-3.5" />
            Full Report
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">Rejection Reason</label>
            <div className="relative">
              <select
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="w-full appearance-none px-3 py-2 pr-8 bg-white border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-red-500/20 focus:border-red-500"
              >
                <option value="">Select a reason...</option>
                {REJECTION_REASONS.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
              <ChevronDown className="w-4 h-4 text-gray-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                if (reason) onDecision(site.id, 'rejected', reason);
              }}
              disabled={!reason}
              className={`px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
                reason
                  ? 'bg-red-600 text-white hover:bg-red-700'
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'
              }`}
            >
              Confirm Rejection
            </button>
            <button
              onClick={() => { setShowReject(false); setReason(''); }}
              className="px-3 py-2 text-sm text-gray-500 hover:text-gray-700"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export function ReviewPage() {
  const { data: reports } = useScoutReports();
  const { data: decisions } = useScoutDecisions();
  const submitDecision = useSubmitDecision();

  const pendingReports = (reports || []).filter((r) => r.decision_status === 'pending');

  const handleDecision = (reportId: string, decision: 'approved' | 'rejected' | 'flagged', reason?: string) => {
    submitDecision.mutate({
      report_id: reportId,
      decision,
      rejection_reason: reason,
      decided_by: 'Michael',
    });
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto px-6 py-8">
        {/* Pending */}
        <div className="mb-10">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-2xl font-semibold text-gray-900">Review Queue</h1>
              <p className="text-sm text-gray-500 mt-1">{pendingReports.length} sites pending review</p>
            </div>
          </div>

          {pendingReports.length > 0 ? (
            <div className="space-y-3">
              {pendingReports.map((site) => (
                <PendingCard key={site.id} site={site} onDecision={handleDecision} />
              ))}
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
              <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-3" />
              <p className="text-sm text-gray-500">All caught up! No sites pending review.</p>
            </div>
          )}
        </div>

        {/* Decision History */}
        <div>
          <h2 className="text-base font-semibold text-gray-900 mb-4">Decision History</h2>
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Report</th>
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Decision</th>
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Reason</th>
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">By</th>
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Date</th>
                </tr>
              </thead>
              <tbody>
                {(decisions || []).map((d: ScoutDecision) => (
                  <tr key={d.id} className="border-b border-gray-50 last:border-0">
                    <td className="px-4 py-3 text-sm text-gray-900">
                      <Link to={`/scout/reports/${d.report_id}`} className="hover:text-red-600">
                        {d.report_id}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${
                        d.decision === 'approved'
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : d.decision === 'rejected'
                          ? 'bg-red-50 text-red-700 border-red-200'
                          : 'bg-amber-50 text-amber-700 border-amber-200'
                      }`}>
                        {d.decision === 'approved' ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                        {d.decision.charAt(0).toUpperCase() + d.decision.slice(1)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">{d.rejection_reason || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-500">{d.decided_by || '-'}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 text-xs text-gray-400">
                        <Clock className="w-3 h-3" />
                        {d.decided_at ? new Date(d.decided_at).toLocaleDateString() : '-'}
                      </div>
                    </td>
                  </tr>
                ))}
                {(!decisions || decisions.length === 0) && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-400">
                      No decisions yet.
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
