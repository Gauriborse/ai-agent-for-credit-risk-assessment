/**
 * CrossVerifyPanel
 * ================
 * Displays a structured, read-only summary of the cross-document
 * verification result for a loan applicant.
 *
 * Props:
 *   result   — object returned by POST /kyc/cross-verify
 *   compact  — boolean (default false): use a smaller layout for embedding
 *              in admin tables / modal sidebars
 */

import React, { useState } from 'react';
import {
  ShieldCheck, ShieldAlert, ShieldX, ShieldQuestion,
  CheckCircle2, XCircle, AlertCircle, Clock,
  ChevronDown, ChevronUp, FileText, User, CreditCard,
  Camera, DollarSign, RefreshCcw, Info
} from 'lucide-react';

// ── Status icon + colour map ───────────────────────────────
const STATUS_MAP = {
  verified: {
    icon:  CheckCircle2,
    color: 'text-emerald-400',
    bg:    'bg-emerald-500/10 border-emerald-500/25',
    badge: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    label: 'Verified',
  },
  partially_verified: {
    icon:  AlertCircle,
    color: 'text-amber-400',
    bg:    'bg-amber-500/10 border-amber-500/25',
    badge: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    label: 'Partially Verified',
  },
  unable_to_verify: {
    icon:  ShieldQuestion,
    color: 'text-slate-400',
    bg:    'bg-slate-500/10 border-slate-500/25',
    badge: 'bg-slate-500/15 text-slate-400 border-slate-500/30',
    label: 'Unable to Verify',
  },
  mismatch: {
    icon:  XCircle,
    color: 'text-red-400',
    bg:    'bg-red-500/10 border-red-500/25',
    badge: 'bg-red-500/15 text-red-400 border-red-500/30',
    label: 'Mismatch',
  },
  manual_review: {
    icon:  AlertCircle,
    color: 'text-amber-400',
    bg:    'bg-amber-500/10 border-amber-500/25',
    badge: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    label: 'Manual Review',
  },
  pending: {
    icon:  Clock,
    color: 'text-slate-500',
    bg:    'bg-slate-800/40 border-slate-700/30',
    badge: 'bg-slate-700/30 text-slate-500 border-slate-600/30',
    label: 'Pending',
  },
};

// Overall status → hero icon
const OVERALL_ICON = {
  verified:           ShieldCheck,
  partially_verified: ShieldAlert,
  unable_to_verify:   ShieldQuestion,
  mismatch:           ShieldX,
  manual_review:      ShieldAlert,
  pending:            ShieldQuestion,
};

function StatusBadge({ status, small = false }) {
  const s   = STATUS_MAP[status] ?? STATUS_MAP.pending;
  const Ico = s.icon;
  return (
    <span className={`inline-flex items-center gap-1 border rounded-full font-bold
      ${small ? 'text-[10px] px-2 py-0.5' : 'text-xs px-2.5 py-1'} ${s.badge}`}>
      <Ico className={small ? 'w-2.5 h-2.5' : 'w-3.5 h-3.5'} />
      {s.label}
    </span>
  );
}

// ── Single check row ──────────────────────────────────────
function CheckRow({ icon: Icon, label, check }) {
  if (!check) return null;
  const s = STATUS_MAP[check.status] ?? STATUS_MAP.pending;
  return (
    <div className={`flex items-start gap-3 rounded-xl px-4 py-3 border ${s.bg}`}>
      <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${s.color}`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap mb-0.5">
          <p className="text-xs font-bold uppercase tracking-wider text-slate-400">{label}</p>
          <StatusBadge status={check.status} small />
          {check.ocr_mode === 'demo' && (
            <span className="text-[9px] text-slate-600 border border-slate-700/40 rounded-full px-1.5 py-0.5">
              OCR demo
            </span>
          )}
          {check.ocr_mode === 'live' && (
            <span className="text-[9px] text-emerald-700 border border-emerald-800/40 rounded-full px-1.5 py-0.5">
              OCR live
            </span>
          )}
        </div>
        {check.message && (
          <p className={`text-xs leading-relaxed ${s.color}`}>{check.message}</p>
        )}
        {check.confidence > 0 && (
          <p className="text-[10px] text-slate-600 mt-0.5">
            Confidence: {Math.round(check.confidence * 100)}%
          </p>
        )}
      </div>
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────
export default function CrossVerifyPanel({ result, compact = false }) {
  const [expanded, setExpanded] = useState(!compact);

  if (!result) return null;

  const overall = result.overall_status ?? 'pending';
  const s       = STATUS_MAP[overall] ?? STATUS_MAP.pending;
  const OvIcon  = OVERALL_ICON[overall] ?? ShieldQuestion;
  const checks  = result.checks ?? {};
  const flags   = result.flags ?? [];
  const isMock  = result.mock_mode;

  return (
    <div className={`backdrop-blur-md border rounded-2xl overflow-hidden ${s.bg}`}>

      {/* ── Header ── */}
      <div
        className={`flex items-center justify-between px-5 py-4 cursor-pointer ${compact ? '' : 'border-b border-white/5'}`}
        onClick={() => setExpanded(e => !e)}
      >
        <div className="flex items-center gap-3">
          <OvIcon className={`w-5 h-5 ${s.color}`} />
          <div>
            <p className="text-white font-bold text-sm">Cross-Document Verification</p>
            <div className="flex items-center gap-2 mt-0.5 flex-wrap">
              <StatusBadge status={overall} />
              {isMock && (
                <span className="text-[10px] text-slate-500 border border-slate-700/40 rounded-full px-1.5 py-0.5">
                  OCR unavailable · demo mode
                </span>
              )}
            </div>
          </div>
        </div>
        <button className="text-slate-500 hover:text-white transition-colors">
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {/* ── Summary message ── */}
      {result.overall_message && (
        <div className={`px-5 ${expanded ? 'pt-4' : 'pb-4 pt-0'}`}>
          <p className={`text-xs leading-relaxed ${s.color}`}>{result.overall_message}</p>
        </div>
      )}

      {/* ── Flags ── */}
      {flags.length > 0 && expanded && (
        <div className="px-5 pb-3">
          <div className="bg-red-500/8 border border-red-500/20 rounded-xl px-4 py-3">
            <p className="text-red-400 text-xs font-bold uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <AlertCircle className="w-3.5 h-3.5" /> Issues Flagged
            </p>
            <ul className="space-y-1">
              {flags.map((f, i) => (
                <li key={i} className="text-red-300 text-xs flex items-start gap-1.5">
                  <span className="text-red-400 mt-0.5 shrink-0">•</span>
                  {f}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* ── Per-check details ── */}
      {expanded && (
        <div className="px-5 pb-5 space-y-2">
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 pt-1 pb-1">
            Verification Checks
          </p>

          <CheckRow
            icon={User}
            label="KYC Document · Name"
            check={checks.kyc_name}
          />
          <CheckRow
            icon={CreditCard}
            label="KYC Document · ID Number"
            check={checks.kyc_id_number}
          />
          <CheckRow
            icon={Camera}
            label="KYC Document · Photograph Presence"
            check={checks.kyc_photo}
          />
          <CheckRow
            icon={Camera}
            label="Selfie vs ID Photo · Face Match"
            check={checks.kyc_selfie_match}
          />
          <CheckRow
            icon={FileText}
            label="Payslip · Employee Name"
            check={checks.payslip_name}
          />
          <CheckRow
            icon={DollarSign}
            label="Payslip · Income"
            check={checks.payslip_income}
          />
          <CheckRow
            icon={RefreshCcw}
            label="Cross-Document · Name Consistency"
            check={checks.name_consistency}
          />

          {/* Mock mode notice */}
          {isMock && (
            <div className="flex items-start gap-2 bg-slate-800/40 border border-slate-700/30 rounded-xl px-4 py-3 mt-2">
              <Info className="w-3.5 h-3.5 text-slate-500 shrink-0 mt-0.5" />
              <p className="text-slate-500 text-xs leading-relaxed">
                OCR (Tesseract) is not installed in this environment. Name and ID number
                extraction from documents could not be performed. These checks will require
                manual review. All other checks (income comparison, photo detection) ran
                with available data.
              </p>
            </div>
          )}

          {/* Re-upload nudge when mismatch is confirmed */}
          {overall === 'mismatch' && flags.length > 0 && (
            <div className="flex items-start gap-2 bg-red-500/8 border border-red-500/25 rounded-xl px-4 py-3 mt-1">
              <Info className="w-3.5 h-3.5 text-red-400 shrink-0 mt-0.5" />
              <p className="text-red-300 text-xs leading-relaxed">
                One or more mismatches were detected. You may re-upload the affected document
                to correct this. Your loan application will not be automatically rejected —
                a staff member will review the flagged items.
              </p>
            </div>
          )}

          {/* Unable to verify — admin review note */}
          {overall === 'unable_to_verify' && (
            <div className="flex items-start gap-2 bg-slate-800/40 border border-slate-600/30 rounded-xl px-4 py-3 mt-1">
              <Info className="w-3.5 h-3.5 text-slate-400 shrink-0 mt-0.5" />
              <p className="text-slate-400 text-xs leading-relaxed">
                Some checks could not run automatically (e.g. OCR unavailable). Your documents
                will be reviewed manually. This does not automatically reject your application.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
