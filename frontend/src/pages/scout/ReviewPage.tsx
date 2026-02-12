import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  CheckCircle2,
  XCircle,
  Flag,
  FileText,
  Clock,
  X,
  AlertTriangle,
} from 'lucide-react';
import { useScoutReports, useScoutDecisions, useSubmitDecision } from '../../hooks/useScout';
import type { ScoutReport, ScoutDecision } from '../../types/store';

const DEMO_BANNER_KEY = 'csoki-review-demo-dismissed';

const FEEDBACK_CHIPS: Record<string, string[]> = {
  approved: [
    'Strong traffic corridor',
    'Ideal demographics',
    'Good anchor proximity',
    'Low competition density',
  ],
  rejected: [
    'Too close to competitor',
    'Weak demographics',
    'Poor visibility/access',
    'Unfavorable lease terms',
  ],
  flagged: [
    'Needs site visit',
    'Zoning verification needed',
    'Lease terms unclear',
    'Market conditions changing',
  ],
};

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
  onDecision: (reportId: string, decision: 'approved' | 'rejected' | 'flagged', notes: string, reason?: string) => void;
}) {
  const [activeDecision, setActiveDecision] = useState<'approved' | 'rejected' | 'flagged' | null>(null);
  const [notes, setNotes] = useState('');
  const [reason, setReason] = useState('');

  const chips = activeDecision ? FEEDBACK_CHIPS[activeDecision] : [];
  const canSubmit = notes.trim().length >= 10 && (activeDecision !== 'rejected' || reason);

  const appendChip = (chip: string) => {
    const sep = notes.trim() ? '. ' : '';
    setNotes((prev) => prev.trim() + sep + chip);
  };

  const reset = () => {
    setActiveDecision(null);
    setNotes('');
    setReason('');
  };

  const handleSubmit = () => {
    if (!activeDecision || !canSubmit) return;
    onDecision(site.id, activeDecision, notes.trim(), activeDecision === 'rejected' ? reason : undefined);
    reset();
  };

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

      {/* Decision selection or feedback form */}
      {!activeDecision ? (
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveDecision('approved')}
            className="flex items-center gap-1.5 px-3 py-2 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-700 transition-colors"
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            Approve
          </button>
          <button
            onClick={() => setActiveDecision('rejected')}
            className="flex items-center gap-1.5 px-3 py-2 border border-red-200 text-red-700 text-sm font-medium rounded-lg hover:bg-red-50 transition-colors"
          >
            <XCircle className="w-3.5 h-3.5" />
            Reject
          </button>
          <button
            onClick={() => setActiveDecision('flagged')}
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
          <div className="flex items-center gap-2">
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${
              activeDecision === 'approved'
                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                : activeDecision === 'rejected'
                ? 'bg-red-50 text-red-700 border-red-200'
                : 'bg-amber-50 text-amber-700 border-amber-200'
            }`}>
              {activeDecision.charAt(0).toUpperCase() + activeDecision.slice(1)}
            </span>
            <button onClick={reset} className="text-xs text-gray-400 hover:text-gray-600">Change</button>
          </div>

          {/* Rejection reason (only for reject) */}
          {activeDecision === 'rejected' && (
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1.5">Rejection Reason</label>
              <select
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="w-full appearance-none px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-red-500/20 focus:border-red-500"
              >
                <option value="">Select a reason...</option>
                {REJECTION_REASONS.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>
          )}

          {/* Feedback chips */}
          <div className="flex flex-wrap gap-1.5">
            {chips.map((chip) => (
              <button
                key={chip}
                onClick={() => appendChip(chip)}
                className="px-2.5 py-1 text-xs font-medium text-gray-600 bg-gray-100 rounded-full hover:bg-gray-200 transition-colors"
              >
                {chip}
              </button>
            ))}
          </div>

          {/* Feedback textarea */}
          <div>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Provide feedback for this decision (min 10 characters)..."
              rows={3}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-red-500/20 focus:border-red-500 placeholder-gray-400 resize-none"
            />
            <p className={`text-xs mt-1 ${notes.trim().length >= 10 ? 'text-emerald-500' : 'text-gray-400'}`}>
              {notes.trim().length}/10 characters minimum
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleSubmit}
              disabled={!canSubmit}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                canSubmit
                  ? activeDecision === 'approved'
                    ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                    : activeDecision === 'rejected'
                    ? 'bg-red-600 text-white hover:bg-red-700'
                    : 'bg-amber-600 text-white hover:bg-amber-700'
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'
              }`}
            >
              Confirm {activeDecision.charAt(0).toUpperCase() + activeDecision.slice(1)}
            </button>
            <button
              onClick={reset}
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
  const { data: reports, isError: reportsError } = useScoutReports();
  const { data: decisions, isError: decisionsError } = useScoutDecisions();
  const submitDecision = useSubmitDecision();
  const [demoDismissed, setDemoDismissed] = useState(() => {
    try { return localStorage.getItem(DEMO_BANNER_KEY) === 'true'; } catch { return false; }
  });

  const dismissDemo = () => {
    setDemoDismissed(true);
    try { localStorage.setItem(DEMO_BANNER_KEY, 'true'); } catch { /* ignore */ }
  };

  const pendingReports = (reports || []).filter((r) => r.decision_status === 'pending');

  const handleDecision = (reportId: string, decision: 'approved' | 'rejected' | 'flagged', notes: string, reason?: string) => {
    submitDecision.mutate({
      report_id: reportId,
      decision,
      rejection_reason: reason,
      notes,
      decided_by: 'Michael',
    });
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto px-6 py-8">
        {/* Error banner */}
        {(reportsError || decisionsError) && (
          <div className="flex items-center gap-3 p-3 mb-6 bg-red-50 border border-red-200 rounded-lg">
            <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0" />
            <p className="text-sm text-red-700 flex-1">
              Unable to connect to SCOUT backend. Reports will appear once the service is running.
            </p>
          </div>
        )}

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
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Feedback</th>
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
                    <td className="px-4 py-3 text-sm text-gray-500 max-w-xs truncate">
                      {d.notes || d.rejection_reason || '-'}
                    </td>
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
