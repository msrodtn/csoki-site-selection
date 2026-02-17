import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft,
  DollarSign,
  FileCheck,
  MessageSquare,
  TrendingUp,
  Building,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  ChevronDown,
} from 'lucide-react';
import { useState } from 'react';
import { useScoutReport, useSubmitDecision } from '../../hooks/useScout';
import type { ScoutAgentDetail } from '../../types/store';

const ICON_MAP: Record<string, React.ElementType> = {
  DollarSign,
  FileCheck,
  TrendingUp,
  Building,
  MessageSquare,
  ShieldCheck,
};

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

function AgentCard({ agent }: { agent: ScoutAgentDetail }) {
  const [expanded, setExpanded] = useState(false);
  const Icon = ICON_MAP[agent.icon] || ShieldCheck;
  const score = agent.score ?? 0;
  const scoreColor = score >= 8 ? 'text-emerald-600' : score >= 6 ? 'text-amber-600' : 'text-red-600';
  const barColor = score >= 8 ? 'bg-emerald-500' : score >= 6 ? 'bg-amber-500' : 'bg-red-500';

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-4 hover:bg-gray-50 transition-colors"
      >
        <div className="w-8 h-8 rounded-lg bg-gray-50 flex items-center justify-center flex-shrink-0">
          <Icon className="w-4 h-4 text-gray-500" />
        </div>
        <span className="text-sm font-medium text-gray-900 flex-1 text-left">{agent.label}</span>
        <div className="flex items-center gap-3">
          <div className="w-20 bg-gray-100 rounded-full h-2">
            <div className={`h-2 rounded-full ${barColor}`} style={{ width: `${score * 10}%` }} />
          </div>
          <span className={`text-sm font-semibold tabular-nums w-12 text-right ${scoreColor}`}>
            {score.toFixed(1)}/10
          </span>
          <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`} />
        </div>
      </button>
      {expanded && (
        <div className="px-4 pb-4 border-t border-gray-100 pt-3">
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 mb-3">
            {Object.entries(agent.details).map(([key, value]) => (
              <div key={key} className="flex justify-between text-sm">
                <span className="text-gray-500">{key}</span>
                <span className="text-gray-900 font-medium">{value}</span>
              </div>
            ))}
          </div>
          {(agent.strengths?.length ?? 0) > 0 && (
            <div className="mt-3">
              {agent.strengths.map((s, i) => (
                <div key={i} className="flex items-start gap-2 text-sm text-emerald-700 mb-1">
                  <CheckCircle2 className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                  <span>{s}</span>
                </div>
              ))}
            </div>
          )}
          {(agent.flags?.length ?? 0) > 0 && (
            <div className="mt-2">
              {agent.flags.map((f, i) => (
                <div key={i} className="flex items-start gap-2 text-sm text-amber-700 mb-1">
                  <AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                  <span>[{(f.severity || 'INFO').toUpperCase()}] {f.description}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ReportDetailPage() {
  const { reportId } = useParams();
  const { data: report, isLoading } = useScoutReport(reportId || '');
  const submitDecision = useSubmitDecision();

  const [activeDecision, setActiveDecision] = useState<'approved' | 'rejected' | 'flagged' | null>(null);
  const [notes, setNotes] = useState('');

  const chips = activeDecision ? FEEDBACK_CHIPS[activeDecision] : [];
  const canSubmit = notes.trim().length >= 10;

  const appendChip = (chip: string) => {
    const sep = notes.trim() ? '. ' : '';
    setNotes((prev) => prev.trim() + sep + chip);
  };

  const handleSubmit = () => {
    if (!reportId || !activeDecision || !canSubmit) return;
    submitDecision.mutate({
      report_id: reportId,
      decision: activeDecision,
      notes: notes.trim(),
      decided_by: 'Michael',
    });
    setActiveDecision(null);
    setNotes('');
  };

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <p className="text-gray-400 text-sm">Loading report...</p>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-500 text-sm">Report not found</p>
          <Link to="/scout/reports" className="text-sm text-red-600 hover:text-red-700 mt-2 inline-block">
            Back to Reports
          </Link>
        </div>
      </div>
    );
  }

  const confidence = report.confidence_score ?? 0;
  const confidenceColor = confidence >= 80 ? 'text-emerald-600' : confidence >= 60 ? 'text-amber-600' : 'text-red-600';
  const barColor = confidence >= 80 ? 'bg-emerald-500' : confidence >= 60 ? 'bg-amber-500' : 'bg-red-500';

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto px-6 py-8">
        {/* Back link */}
        <Link to="/scout/reports" className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-6">
          <ArrowLeft className="w-4 h-4" />
          Back to Reports
        </Link>

        {/* Header */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-xl font-semibold text-gray-900">{report.site_address}</h1>
              <p className="text-sm text-gray-500 mt-1">
                {report.market} &middot; {report.created_at ? new Date(report.created_at).toLocaleDateString() : ''}
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Confidence</p>
              <p className={`text-3xl font-bold tabular-nums ${confidenceColor}`}>{confidence}%</p>
            </div>
          </div>
          <div className="mt-4">
            <div className="w-full bg-gray-100 rounded-full h-3">
              <div className={`h-3 rounded-full ${barColor} transition-all`} style={{ width: `${confidence}%` }} />
            </div>
          </div>
        </div>

        {/* Agent Breakdown */}
        {report.agent_details && (
          <div className="mb-6">
            <h2 className="text-base font-semibold text-gray-900 mb-3">Agent Breakdown</h2>
            <div className="space-y-2">
              {Object.values(report.agent_details).map((agent) => (
                <AgentCard key={agent.label} agent={agent} />
              ))}
            </div>
          </div>
        )}

        {/* Strengths & Flags side by side */}
        <div className="grid grid-cols-2 gap-4 mb-8">
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Strengths</h3>
            <div className="space-y-2">
              {(report.strengths || []).map((s, i) => (
                <div key={i} className="flex items-start gap-2 text-sm text-emerald-700">
                  <CheckCircle2 className="w-4 h-4 mt-0.5 flex-shrink-0 text-emerald-500" />
                  <span>{s}</span>
                </div>
              ))}
              {(!report.strengths || report.strengths.length === 0) && (
                <p className="text-sm text-gray-400">No strengths identified</p>
              )}
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Flags</h3>
            {(report.flags || []).length > 0 ? (
              <div className="space-y-2">
                {report.flags!.map((f, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm text-amber-700">
                    <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0 text-amber-500" />
                    <span>[{(f.severity || 'INFO').toUpperCase()}] {f.description}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-400">No flags raised</p>
            )}
          </div>
        </div>

        {/* Decision Section */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Decision</h3>
          {report.decision_status !== 'pending' ? (
            <p className="text-sm text-gray-500">
              This report has been <strong>{report.decision_status}</strong>.
            </p>
          ) : !activeDecision ? (
            <div>
              <p className="text-xs text-gray-500 mb-3">Select a decision, then provide feedback before confirming.</p>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setActiveDecision('approved')}
                  className="flex-1 px-4 py-2.5 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-700 transition-colors"
                >
                  Approve
                </button>
                <button
                  onClick={() => setActiveDecision('rejected')}
                  className="flex-1 px-4 py-2.5 bg-white border border-red-200 text-red-700 text-sm font-medium rounded-lg hover:bg-red-50 transition-colors"
                >
                  Reject
                </button>
                <button
                  onClick={() => setActiveDecision('flagged')}
                  className="flex-1 px-4 py-2.5 bg-white border border-gray-200 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Flag for Review
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
                  activeDecision === 'approved'
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : activeDecision === 'rejected'
                    ? 'bg-red-50 text-red-700 border-red-200'
                    : 'bg-amber-50 text-amber-700 border-amber-200'
                }`}>
                  {activeDecision.charAt(0).toUpperCase() + activeDecision.slice(1)}
                </span>
                <button
                  onClick={() => { setActiveDecision(null); setNotes(''); }}
                  className="text-xs text-gray-400 hover:text-gray-600"
                >
                  Change
                </button>
              </div>

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
                  disabled={!canSubmit || submitDecision.isPending}
                  className={`px-4 py-2.5 text-sm font-medium rounded-lg transition-colors ${
                    canSubmit && !submitDecision.isPending
                      ? activeDecision === 'approved'
                        ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                        : activeDecision === 'rejected'
                        ? 'bg-red-600 text-white hover:bg-red-700'
                        : 'bg-amber-600 text-white hover:bg-amber-700'
                      : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  }`}
                >
                  {submitDecision.isPending ? 'Submitting...' : `Confirm ${activeDecision.charAt(0).toUpperCase() + activeDecision.slice(1)}`}
                </button>
                <button
                  onClick={() => { setActiveDecision(null); setNotes(''); }}
                  className="px-3 py-2 text-sm text-gray-500 hover:text-gray-700"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
