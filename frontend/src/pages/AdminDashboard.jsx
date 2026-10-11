import React, { useState, useEffect } from 'react';
import {
  ShieldCheck, LogOut, Users, CheckCircle, XCircle,
  Clock, Activity, RefreshCcw, ChevronDown, ChevronUp,
  TrendingUp, AlertTriangle, FileText, Eye, X,
  Phone, Mail, AlertCircle, ThumbsUp, ThumbsDown,
  BarChart2, Info, ScanLine, CreditCard
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

// ── KYC status badge ───────────────────────────────────────
function KYCBadge({ status, idType }) {
  const map = {
    verified:     { cls: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30', label: 'Verified' },
    format_valid: { cls: 'bg-blue-500/15 text-blue-400 border-blue-500/30',          label: 'Format ✓' },
    pending:      { cls: 'bg-slate-500/15 text-slate-400 border-slate-500/30',       label: 'Pending' },
    failed:       { cls: 'bg-red-500/15 text-red-400 border-red-500/30',             label: 'Failed' },
  };
  const idLabels = { aadhaar: 'Aadhaar', pan: 'PAN', dl: 'DL', college: 'College' };
  const s = map[status] ?? map.pending;
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border inline-flex items-center gap-1 ${s.cls}`}>
      <ScanLine className="w-2.5 h-2.5" />
      {s.label}{idType ? ` · ${idLabels[idType] ?? idType}` : ''}
    </span>
  );
}


// ── Stat card ──────────────────────────────────────────────
function StatCard({ icon: Icon, label, value, color, sub }) {
  return (
    <div className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-6 flex items-start gap-4 hover:border-white/20 transition-all">
      <div className={`p-3 rounded-xl ${color}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-1">{label}</p>
        <p className="text-3xl font-black text-white">{value}</p>
        {sub && <p className="text-slate-500 text-xs mt-1">{sub}</p>}
      </div>
    </div>
  );
}

// ── Decision badge ─────────────────────────────────────────
function DecisionBadge({ decision, override }) {
  const map = {
    Approve: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    Reject:  'bg-red-500/15 text-red-400 border-red-500/30',
    Review:  'bg-amber-500/15 text-amber-400 border-amber-500/30',
  };
  return (
    <span className={`px-2.5 py-1 rounded-full text-xs font-bold border inline-flex items-center gap-1.5 ${map[decision] ?? 'bg-slate-500/15 text-slate-400 border-slate-500/30'}`}>
      {decision}
      {override && <span className="text-[9px] opacity-70 font-normal">(Admin)</span>}
    </span>
  );
}

// ── Risk meter bar ─────────────────────────────────────────
function RiskBar({ value }) {
  const pct = Math.round(value * 100);
  const color = value < 0.4 ? 'bg-emerald-500' : value < 0.7 ? 'bg-amber-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-slate-800 rounded-full h-2">
        <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-slate-400 w-10 text-right">{pct}%</span>
    </div>
  );
}

// ── Review Modal ───────────────────────────────────────────
function ReviewModal({ app, onClose, onDecision }) {
  const [note, setNote]         = useState('');
  const [submitting, setSub]    = useState(false);
  const [chosen, setChosen]     = useState(null); // 'Approve' | 'Reject'
  const d = app.application_data || {};
  const features = app.important_features || [];

  const submit = async (decision) => {
    setChosen(decision);
    setSub(true);
    try {
      await api.patch(`/admin/applications/${app._id}/decision`, {
        decision,
        admin_note: note,
      });
      onDecision(app._id, decision, note);
    } catch (e) {
      alert('Failed to save decision. Please try again.');
    } finally {
      setSub(false);
    }
  };

  // risk zone label
  const riskPct  = Math.round((app.risk_score ?? 0) * 100);
  const riskZone = app.risk_score < 0.4 ? { label: 'Low Risk', color: 'text-emerald-400' }
                 : app.risk_score < 0.7 ? { label: 'Moderate Risk', color: 'text-amber-400' }
                 :                        { label: 'High Risk',     color: 'text-red-400' };

  return (
    /* backdrop */
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto backdrop-blur-xl bg-slate-900 border border-white/10 rounded-3xl shadow-2xl">

        {/* Modal header */}
        <div className="flex items-center justify-between p-6 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="bg-amber-500/15 p-2 rounded-xl border border-amber-500/30">
              <AlertCircle className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <h2 className="text-lg font-black text-white">Manual Review</h2>
              <p className="text-slate-400 text-xs mt-0.5">Application ID: <span className="font-mono text-amber-400">{app.user_id}</span></p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors p-2 rounded-lg hover:bg-white/5">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-6">

          {/* ── KYC status in review modal ── */}
          {(() => {
            const kycStatus = app.kyc_status || (app.application_data || {}).kyc_status || 'pending';
            const kycIdType = app.kyc_id_type || (app.application_data || {}).kyc_id_type || null;
            const cvStatus  = (app.application_data || {}).cross_verify_status;
            const cvFlags   = (app.application_data || {}).cross_verify_flags || [];
            return (
              <div className="space-y-3">
                {/* KYC agent result */}
                <div className="bg-slate-800/40 border border-white/8 rounded-2xl p-4 flex items-center gap-4">
                  <ScanLine className="w-5 h-5 text-amber-400 shrink-0" />
                  <div className="flex-1">
                    <p className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1">KYC Verification</p>
                    <div className="flex items-center gap-2 flex-wrap">
                      <KYCBadge status={kycStatus} idType={kycIdType} />
                      {kycStatus === 'format_valid' && (
                        <p className="text-amber-300 text-xs">
                          ID format valid but not officially verified — no real identity API called.
                        </p>
                      )}
                      {kycStatus === 'verified' && (
                        <p className="text-emerald-400 text-xs">Face match + liveness check passed.</p>
                      )}
                      {kycStatus === 'pending' && (
                        <p className="text-slate-500 text-xs">Applicant has not completed KYC.</p>
                      )}
                      {kycStatus === 'failed' && (
                        <p className="text-red-400 text-xs">KYC verification failed — review documents carefully.</p>
                      )}
                    </div>
                  </div>
                </div>

                {/* Cross-document verification summary */}
                {cvStatus && (
                  <div className={`border rounded-2xl p-4 ${
                    cvStatus === 'verified'           ? 'bg-emerald-500/8 border-emerald-500/25' :
                    cvStatus === 'mismatch'           ? 'bg-red-500/8 border-red-500/25' :
                    cvStatus === 'partially_verified' ? 'bg-blue-500/8 border-blue-500/20' :
                    cvStatus === 'manual_review'      ? 'bg-amber-500/8 border-amber-500/20' :
                                                        'bg-slate-800/40 border-white/8'
                  }`}>
                    <div className="flex items-center gap-2 mb-2">
                      <Info className="w-4 h-4 text-slate-400 shrink-0" />
                      <p className="text-slate-400 text-xs font-bold uppercase tracking-wider">Cross-Document Verification</p>
                      <span className={`ml-auto text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                        cvStatus === 'verified'           ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' :
                        cvStatus === 'mismatch'           ? 'bg-red-500/15 text-red-400 border-red-500/30' :
                        cvStatus === 'partially_verified' ? 'bg-blue-500/15 text-blue-400 border-blue-500/30' :
                        cvStatus === 'manual_review'      ? 'bg-amber-500/15 text-amber-400 border-amber-500/30' :
                                                            'bg-slate-700/30 text-slate-400 border-slate-600/30'
                      }`}>
                        {cvStatus.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                      </span>
                    </div>
                    {cvFlags.length > 0 && (
                      <ul className="space-y-1 mt-1">
                        {cvFlags.map((f, i) => (
                          <li key={i} className="text-xs flex items-start gap-1.5 text-red-300/80">
                            <span className="text-red-400 mt-0.5 shrink-0">•</span> {f}
                          </li>
                        ))}
                      </ul>
                    )}
                    {cvFlags.length === 0 && cvStatus === 'verified' && (
                      <p className="text-emerald-400 text-xs">All cross-document checks passed.</p>
                    )}
                    {cvStatus === 'mismatch' && (
                      <p className="text-red-300 text-xs mt-1">
                        This application has been flagged for manual review due to document mismatches.
                        Review the flagged items above before approving.
                      </p>
                    )}
                    {(cvStatus === 'unable_to_verify' || cvStatus === 'partially_verified') && (
                      <p className="text-slate-400 text-xs mt-1">
                        Some checks could not run automatically (OCR unavailable). Manual verification recommended.
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })()}

          {/* ── Why AI flagged for review ── */}
          <div className="bg-amber-500/5 border border-amber-500/20 rounded-2xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <Info className="w-4 h-4 text-amber-400" />
              <p className="text-amber-400 text-xs font-bold uppercase tracking-wider">Why AI Flagged for Manual Review</p>
            </div>
            <p className="text-slate-200 text-sm leading-relaxed">{app.explanation || '—'}</p>
          </div>

          {/* ── Risk snapshot ── */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-white/5 border border-white/10 rounded-xl p-4 text-center">
              <p className="text-slate-500 text-xs uppercase tracking-wider mb-1">Risk Score</p>
              <p className={`text-2xl font-black ${riskZone.color}`}>{riskPct}%</p>
              <p className={`text-xs mt-1 ${riskZone.color}`}>{riskZone.label}</p>
            </div>
            <div className="bg-white/5 border border-white/10 rounded-xl p-4 text-center">
              <p className="text-slate-500 text-xs uppercase tracking-wider mb-1">Confidence</p>
              <p className="text-2xl font-black text-white">{Math.round((app.confidence ?? 0) * 100)}%</p>
              <p className="text-xs text-slate-500 mt-1">AI certainty</p>
            </div>
            <div className="bg-white/5 border border-white/10 rounded-xl p-4 text-center">
              <p className="text-slate-500 text-xs uppercase tracking-wider mb-1">AI Decision</p>
              <p className="text-2xl font-black text-amber-400">Review</p>
              <p className="text-xs text-slate-500 mt-1">borderline case</p>
            </div>
          </div>

          {/* ── Applicant details ── */}
          <div>
            <p className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-3 flex items-center gap-2">
              <Users className="w-3.5 h-3.5" /> Applicant Financial Profile
            </p>
            <div className="grid grid-cols-2 gap-3">
              {[
                ['Name',             d.full_name || d.user_id || '—'],
                ['Age',              d.age ? String(d.age) : '—'],
                ['Monthly Income',   d.income ? (d.currency === 'INR' ? '₹' : '$') + Number(d.income).toLocaleString() : '—'],
                ['Employment Type',  d.employment_type || '—'],
                ['Employment',       d.employment_length != null ? d.employment_length + ' yrs' : '—'],
                ['Loan Amount',      d.loan_amount ? (d.currency === 'INR' ? '₹' : '$') + Number(d.loan_amount).toLocaleString() : '—'],
                ['Tenure',           d.loan_tenure ? d.loan_tenure + ' mo' : '—'],
                ['Purpose',          d.loan_purpose || '—'],
                ['Existing EMI',     d.existing_emi != null ? (d.currency === 'INR' ? '₹' : '$') + Number(d.existing_emi).toLocaleString() : '—'],
                ['DTI (computed)',   d.dti ? (d.dti * 100).toFixed(0) + '%' : '—'],
                ['Risk Category',    d.risk_category || app.risk_category || '—'],
                ['Internal Score',   app.internal_score ? app.internal_score + ' (illustrative)' : '—'],
              ].map(([k, v]) => (
                <div key={k} className="bg-white/5 border border-white/8 rounded-xl px-4 py-3">
                  <p className="text-slate-500 text-xs uppercase tracking-wider mb-0.5">{k}</p>
                  <p className="text-white font-bold text-sm truncate">{v}</p>
                </div>
              ))}
            </div>
          </div>

          {/* ── Fraud flags ── */}
          {app.fraud_flags && app.fraud_flags.length > 0 && (
            <div className="bg-amber-500/5 border border-amber-500/20 rounded-2xl p-4">
              <p className="text-amber-400 text-xs font-bold uppercase tracking-wider mb-2">Anomaly Flags</p>
              <ul className="space-y-1">
                {app.fraud_flags.map((f, i) => (
                  <li key={i} className="text-amber-200/80 text-xs flex items-start gap-1.5">
                    <span className="text-amber-400 mt-0.5">•</span> {f}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* ── Bureau disclaimer ── */}
          {app.credit_bureau_data && app.credit_bureau_data.disclaimer && (
            <div className="bg-slate-800/40 border border-white/5 rounded-xl p-3 text-xs text-slate-500">
              {app.credit_bureau_data.disclaimer}
            </div>
          )}


          {/* ── AI Feature impact ── */}
          {features.length > 0 && (
            <div>
              <p className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-3 flex items-center gap-2">
                <BarChart2 className="w-3.5 h-3.5" /> Key Factors (AI Analysis)
              </p>
              <div className="space-y-2">
                {features.map((f, i) => (
                  <div key={i} className="bg-white/5 border border-white/8 rounded-xl px-4 py-3 flex items-center justify-between">
                    <span className="text-white text-sm font-semibold capitalize">{f.feature?.replace(/_/g, ' ')}</span>
                    <span className={`text-xs font-medium px-2 py-1 rounded-full border ${
                      f.impact?.toLowerCase().includes('positive') || f.impact?.toLowerCase().includes('reducing')
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                        : f.impact?.toLowerCase().includes('negative') || f.impact?.toLowerCase().includes('increasing')
                        ? 'bg-red-500/10 text-red-400 border-red-500/20'
                        : 'bg-slate-500/10 text-slate-400 border-slate-500/20'
                    }`}>
                      {f.impact}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Contact hint ── */}
          <div className="bg-slate-800/60 border border-white/8 rounded-2xl p-4">
            <p className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-2 flex items-center gap-2">
              <Phone className="w-3.5 h-3.5" /> Verification Checklist
            </p>
            <ul className="text-slate-300 text-sm space-y-1.5">
              <li className="flex items-start gap-2"><span className="text-amber-400 mt-0.5">•</span> Contact applicant <span className="font-mono text-amber-400">{app.user_id}</span> to verify financial details</li>
              <li className="flex items-start gap-2"><span className="text-amber-400 mt-0.5">•</span> Confirm income and employment status independently</li>
              <li className="flex items-start gap-2"><span className="text-amber-400 mt-0.5">•</span> Review any supporting documents submitted</li>
              <li className="flex items-start gap-2"><span className="text-amber-400 mt-0.5">•</span> Record your findings in the note below before deciding</li>
            </ul>
          </div>

          {/* ── Admin note ── */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
              Admin Note (optional)
            </label>
            <textarea
              rows={3}
              value={note}
              onChange={e => setNote(e.target.value)}
              placeholder="e.g. Called applicant, confirmed employment at Acme Corp. Income verified via bank statement."
              className="w-full bg-slate-950/60 border border-white/10 rounded-xl p-4 text-white placeholder-slate-600 focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 outline-none transition-all resize-none text-sm"
            />
          </div>

          {/* ── Action buttons ── */}
          <div className="grid grid-cols-2 gap-4 pt-2">
            <button
              disabled={submitting}
              onClick={() => submit('Approve')}
              className="flex items-center justify-center gap-2 bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 hover:border-emerald-500/50 text-emerald-400 font-bold py-4 rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed hover:scale-[1.02] disabled:hover:scale-100"
            >
              {submitting && chosen === 'Approve'
                ? <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></svg>
                : <ThumbsUp className="w-4 h-4" />
              }
              Approve
            </button>
            <button
              disabled={submitting}
              onClick={() => submit('Reject')}
              className="flex items-center justify-center gap-2 bg-red-500/15 hover:bg-red-500/25 border border-red-500/30 hover:border-red-500/50 text-red-400 font-bold py-4 rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed hover:scale-[1.02] disabled:hover:scale-100"
            >
              {submitting && chosen === 'Reject'
                ? <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></svg>
                : <ThumbsDown className="w-4 h-4" />
              }
              Reject
            </button>
          </div>

        </div>
      </div>
    </div>
  );
}

// ── Application row ────────────────────────────────────────
function AppRow({ app, index, onReview }) {
  const [open, setOpen] = useState(false);
  const d = app.application_data || {};
  const isReview = app.decision === 'Review';
  const kycStatus = app.kyc_status || d.kyc_status || 'pending';
  const kycIdType = app.kyc_id_type || d.kyc_id_type || null;

  return (
    <>
      <tr
        className={`border-b border-white/5 hover:bg-white/5 cursor-pointer transition-colors ${isReview ? 'bg-amber-500/3' : ''}`}
        onClick={() => setOpen(o => !o)}
      >
        <td className="px-4 py-3 text-slate-400 text-sm font-mono">{index + 1}</td>
        <td className="px-4 py-3 text-white text-sm font-semibold">{app.user_id}</td>
        <td className="px-4 py-3">
          <DecisionBadge decision={app.decision} override={app.admin_override} />
        </td>
        <td className="px-4 py-3 text-slate-300 text-sm w-32">
          <RiskBar value={app.risk_score ?? 0} />
        </td>
        <td className="px-4 py-3 text-slate-300 text-sm">
          {Math.round((app.confidence ?? 0) * 100)}%
        </td>
        <td className="px-4 py-3">
          <KYCBadge status={kycStatus} idType={kycIdType} />
        </td>
        <td className="px-4 py-3 text-slate-400 text-xs">
          {app.timestamp ? new Date(app.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'}
        </td>
        <td className="px-4 py-3">
          <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
            {isReview && (
              <button
                onClick={() => onReview(app)}
                className="flex items-center gap-1.5 text-xs font-bold text-amber-400 bg-amber-400/10 border border-amber-400/30 hover:bg-amber-400/20 px-3 py-1.5 rounded-lg transition-all"
              >
                <Eye className="w-3.5 h-3.5" /> Review
              </button>
            )}
            <button
              onClick={() => setOpen(o => !o)}
              className="text-slate-500 hover:text-white transition-colors"
            >
              {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
          </div>
        </td>
      </tr>

      {open && (
        <tr className="bg-slate-900/60">
          <td colSpan={8} className="px-6 py-4">
            {/* KYC status row */}
            <div className="flex items-center gap-3 mb-3 bg-white/3 border border-white/8 rounded-xl px-4 py-2.5">
              <ScanLine className="w-3.5 h-3.5 text-amber-400 shrink-0" />
              <p className="text-slate-400 text-xs uppercase tracking-wider font-bold">KYC</p>
              <KYCBadge status={kycStatus} idType={kycIdType} />
              {kycStatus === 'format_valid' && (
                <p className="text-slate-500 text-xs ml-2">
                  Format-only check — not officially verified. Admin review recommended.
                </p>
              )}
              {kycStatus === 'pending' && (
                <p className="text-slate-500 text-xs ml-2">KYC not yet completed by applicant.</p>
              )}
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 text-sm mb-3">
              {[
                ['Income',       d.income ? (d.currency === 'INR' ? '₹' : '$') + Number(d.income).toLocaleString() : '—'],
                ['Employment',   d.employment_type || '—'],
                ['Loan Amount',  d.loan_amount ? (d.currency === 'INR' ? '₹' : '$') + Number(d.loan_amount).toLocaleString() : '—'],
                ['Tenure',       d.loan_tenure ? d.loan_tenure + ' mo' : '—'],
                ['Risk Category', d.risk_category || app.risk_category || '—'],
              ].map(([k, v]) => (
                <div key={k}>
                  <p className="text-slate-500 text-xs uppercase tracking-wider mb-0.5">{k}</p>
                  <p className="text-white font-semibold">{v}</p>
                </div>
              ))}
            </div>
            <div className="bg-slate-800/60 border border-white/5 rounded-xl p-3 mb-2">
              <p className="text-slate-500 text-xs uppercase tracking-wider mb-1">AI Explanation</p>
              <p className="text-slate-300 text-sm leading-relaxed">{app.explanation || '—'}</p>
            </div>
            {app.admin_note && (
              <div className="bg-indigo-500/5 border border-indigo-500/20 rounded-xl p-3">
                <p className="text-indigo-400 text-xs uppercase tracking-wider mb-1 font-bold">Admin Note</p>
                <p className="text-slate-300 text-sm">{app.admin_note}</p>
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

// ── Main Admin Dashboard ───────────────────────────────────
export default function AdminDashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [applications, setApplications] = useState([]);
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState(null);
  const [filter, setFilter]             = useState('All');
  const [refreshing, setRefreshing]     = useState(false);
  const [reviewApp, setReviewApp]       = useState(null); // app open in modal
  const [newCount, setNewCount]         = useState(0);    // badge for new arrivals
  const prevCountRef                    = React.useRef(0);

  const fetchApplications = async (showSpin = false) => {
    if (showSpin) setRefreshing(true);
    else if (loading) setLoading(true);
    setError(null);
    try {
      const res = await api.get('/admin/applications');
      const incoming = res.data ?? [];
      setApplications(incoming);

      // Show "new applications" badge if count grew since last fetch
      if (prevCountRef.current > 0 && incoming.length > prevCountRef.current) {
        setNewCount(incoming.length - prevCountRef.current);
      }
      prevCountRef.current = incoming.length;
    } catch {
      setError('Could not load applications. Make sure the backend is running.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  // Initial load + auto-poll every 15 seconds for new submissions
  useEffect(() => {
    fetchApplications();
    const timer = setInterval(() => fetchApplications(false), 15000);
    return () => clearInterval(timer);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // After admin makes a decision, update local state immediately
  const handleDecision = (id, newDecision, note) => {
    setApplications(prev =>
      prev.map(a => a._id === id ? { ...a, decision: newDecision, admin_override: true, admin_note: note } : a)
    );
    setReviewApp(null);
  };

  const handleLogout = () => { logout(); navigate('/login'); };

  const total    = applications.length;
  const approved = applications.filter(a => a.decision === 'Approve').length;
  const rejected = applications.filter(a => a.decision === 'Reject').length;
  const review   = applications.filter(a => a.decision === 'Review').length;
  const avgRisk  = total ? (applications.reduce((s, a) => s + (a.risk_score ?? 0), 0) / total * 100).toFixed(1) : '0.0';

  const filterOptions = ['All', 'Review', 'Approve', 'Reject'];
  const visible = filter === 'All' ? applications : applications.filter(a => a.decision === filter);

  return (
    <div className="min-h-screen pb-20">

      {/* Review modal */}
      {reviewApp && (
        <ReviewModal
          app={reviewApp}
          onClose={() => setReviewApp(null)}
          onDecision={handleDecision}
        />
      )}

      {/* ── Top bar ── */}
      <header className="sticky top-0 z-40 border-b border-white/10 bg-slate-950/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-gradient-to-br from-amber-400 to-amber-600 p-2 rounded-xl shadow-lg shadow-amber-500/20">
              <ShieldCheck className="w-5 h-5 text-slate-950" />
            </div>
            <div>
              <span className="text-lg font-bold text-white tracking-tight">
                LoanRisk<span className="text-amber-400">AI</span>
              </span>
              <span className="ml-2 text-xs font-bold uppercase tracking-widest bg-amber-400/15 text-amber-400 border border-amber-400/30 px-2 py-0.5 rounded-full">
                Admin
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {review > 0 && (
              <button
                onClick={() => setFilter('Review')}
                className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-bold animate-pulse"
              >
                <Clock className="w-3.5 h-3.5" />
                {review} Pending Review
              </button>
            )}
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              Live
            </div>
            <span className="hidden sm:block text-slate-400 text-sm">{user?.name}</span>
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 text-sm font-semibold text-slate-400 hover:text-red-400 px-4 py-2 rounded-lg hover:bg-red-500/10 transition-all border border-white/10"
            >
              <LogOut className="w-4 h-4" /> Logout
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-10">

        <div className="mb-8">
          <h1 className="text-2xl font-black text-white">Admin Dashboard</h1>
          <p className="text-slate-400 text-sm mt-1">Overview of all loan applications processed by the AI engine.</p>
        </div>

        {/* ── Stat cards ── */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-10">
          <StatCard icon={FileText}    label="Total"         value={total}          color="bg-slate-700/60 text-slate-300"      sub="all applications" />
          <StatCard icon={CheckCircle} label="Approved"      value={approved}       color="bg-emerald-500/15 text-emerald-400"  sub={total ? `${(approved/total*100).toFixed(0)}% of total` : ''} />
          <StatCard icon={XCircle}     label="Rejected"      value={rejected}       color="bg-red-500/15 text-red-400"          sub={total ? `${(rejected/total*100).toFixed(0)}% of total` : ''} />
          <StatCard icon={Clock}       label="Pending Review" value={review}        color="bg-amber-500/15 text-amber-400"      sub="needs admin action" />
          <StatCard icon={TrendingUp}  label="Avg Risk"      value={`${avgRisk}%`}  color="bg-indigo-500/15 text-indigo-400"    sub="mean default probability" />
        </div>

        {/* ── Table card ── */}
        <div className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-3xl shadow-2xl overflow-hidden">

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-6 border-b border-white/10">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Activity className="w-5 h-5 text-amber-400" />
              Application Log
              <span className="text-sm font-normal text-slate-500 ml-1">({visible.length} records)</span>
            </h2>
            <div className="flex items-center gap-3">
              <div className="flex gap-1">
                {filterOptions.map(f => (
                  <button
                    key={f}
                    onClick={() => setFilter(f)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all border ${
                      filter === f
                        ? 'bg-amber-400/20 text-amber-400 border-amber-400/40'
                        : 'text-slate-400 border-white/10 hover:text-white hover:bg-white/5'
                    }`}
                  >
                    {f}{f === 'Review' && review > 0 ? ` (${review})` : ''}
                  </button>
                ))}
              </div>
              <button
                onClick={() => { fetchApplications(true); setNewCount(0); }}
                disabled={refreshing}
                className="flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-white px-3 py-1.5 rounded-lg border border-white/10 hover:bg-white/5 transition-all disabled:opacity-50"
              >
                <RefreshCcw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
                Refresh
                {newCount > 0 && (
                  <span className="ml-1 bg-amber-400 text-slate-900 text-[10px] font-black px-1.5 py-0.5 rounded-full animate-pulse">
                    +{newCount} new
                  </span>
                )}
              </button>
            </div>
          </div>

          {loading ? (
            <div className="flex flex-col items-center justify-center py-24 gap-4">
              <svg className="animate-spin h-8 w-8 text-amber-400" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              <p className="text-slate-500 text-sm">Loading applications…</p>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-20 gap-3">
              <div className="bg-red-500/10 p-4 rounded-2xl"><AlertTriangle className="w-8 h-8 text-red-400" /></div>
              <p className="text-red-400 font-semibold">{error}</p>
              <button onClick={() => fetchApplications()} className="text-sm text-slate-400 hover:text-white underline transition-colors">Try again</button>
            </div>
          ) : visible.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 gap-3 text-slate-500">
              <Users className="w-10 h-10" />
              <p className="font-semibold">No applications found</p>
              <p className="text-sm">Submit a loan application from the user dashboard first.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-white/10 bg-slate-900/40">
                    {['#', 'User ID', 'Decision', 'Risk Score', 'Confidence', 'KYC', 'Date', 'Action'].map(h => (
                      <th key={h} className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-slate-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {visible.map((app, i) => (
                    <AppRow
                      key={app._id ?? i}
                      app={app}
                      index={i}
                      onReview={setReviewApp}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
