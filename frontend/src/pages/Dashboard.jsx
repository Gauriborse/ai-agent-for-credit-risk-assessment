import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity, LogOut, Clock, CheckCircle, XCircle,
  RefreshCcw, ChevronDown, ChevronUp,
  History, ShieldAlert, ScanLine, ChevronRight,
  PlusCircle, ArrowLeft, TrendingUp, DollarSign,
  AlertTriangle, User, Briefcase, CreditCard,
  Calendar, FileText, Upload, X, Zap, Loader2,
  CheckCircle2, Phone, ShieldCheck, ShieldX,
  ShieldQuestion, Info
} from 'lucide-react';
import ResultCard from '../components/ResultCard';
import CollegeKYC from '../components/CollegeKYC';
import api from '../services/api';
import { useAuth } from '../contexts/AuthContext';

// ─────────────────────────────────────────────────────────
//  Constants
// ─────────────────────────────────────────────────────────
const EMPLOYMENT_TYPES = [
  { value: 'salaried',      label: 'Salaried Employee' },
  { value: 'self-employed', label: 'Self Employed' },
  { value: 'business',      label: 'Business Owner' },
  { value: 'student',       label: 'Student' },
  { value: 'unemployed',    label: 'Currently Unemployed' },
];
const LOAN_PURPOSES = [
  { value: 'home',      label: 'Home / Mortgage' },
  { value: 'vehicle',   label: 'Vehicle Purchase' },
  { value: 'education', label: 'Education' },
  { value: 'medical',   label: 'Medical Emergency' },
  { value: 'business',  label: 'Business / Startup' },
  { value: 'personal',  label: 'Personal Use' },
  { value: 'debt',      label: 'Debt Consolidation' },
  { value: 'other',     label: 'Other' },
];

// ─────────────────────────────────────────────────────────
//  Shared form components
// ─────────────────────────────────────────────────────────
function Input({ ...props }) {
  return (
    <input
      className="w-full bg-slate-800/60 border border-white/10 rounded-xl px-4 py-3.5 text-white
                 placeholder-slate-500 focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500
                 outline-none transition-all text-sm disabled:opacity-50"
      {...props}
    />
  );
}
function Select({ children, ...props }) {
  return (
    <select
      className="w-full bg-slate-800/60 border border-white/10 rounded-xl px-4 py-3.5 text-white
                 focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 outline-none
                 transition-all text-sm appearance-none"
      {...props}
    >{children}</select>
  );
}
function Label({ icon: Icon, children, required }) {
  return (
    <label className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
      {Icon && <Icon className="w-3.5 h-3.5" />}
      {children}
      {required && <span className="text-red-400">*</span>}
    </label>
  );
}
function SectionTitle({ step, total, title, subtitle }) {
  return (
    <div className="mb-8">
      <p className="text-amber-400 text-xs font-bold uppercase tracking-widest mb-1">
        Step {step} of {total}
      </p>
      <h2 className="text-3xl font-black text-white">{title}</h2>
      {subtitle && <p className="text-slate-400 mt-1 text-sm">{subtitle}</p>}
    </div>
  );
}

// ─────────────────────────────────────────────────────────
//  Step progress bar
// ─────────────────────────────────────────────────────────
const STEPS = ['KYC', 'Personal', 'Income', 'Loan', 'Result'];

function StepBar({ current }) {
  return (
    <div className="flex items-center gap-0 mb-10">
      {STEPS.map((label, i) => {
        const done    = i < current;
        const active  = i === current;
        const pending = i > current;
        return (
          <React.Fragment key={label}>
            <div className="flex flex-col items-center">
              <div className={`w-9 h-9 rounded-full flex items-center justify-center text-xs font-black border-2 transition-all
                ${done    ? 'bg-emerald-500 border-emerald-500 text-white'
                : active  ? 'bg-amber-400 border-amber-400 text-slate-900'
                           : 'bg-slate-800 border-slate-600 text-slate-500'}`}>
                {done ? <CheckCircle className="w-4 h-4" /> : i + 1}
              </div>
              <span className={`text-[10px] mt-1 font-semibold uppercase tracking-wider
                ${done ? 'text-emerald-400' : active ? 'text-amber-400' : 'text-slate-600'}`}>
                {label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`flex-1 h-0.5 mx-1 mb-4 rounded-full transition-all
                ${i < current ? 'bg-emerald-500' : 'bg-slate-700'}`} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────
//  History card (unchanged logic)
// ─────────────────────────────────────────────────────────
function Badge({ decision, override }) {
  const map = {
    Approve: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    Reject:  'bg-red-500/15 text-red-400 border-red-500/30',
    Review:  'bg-amber-500/15 text-amber-400 border-amber-500/30',
  };
  const icons = { Approve: <CheckCircle className="w-3.5 h-3.5" />, Reject: <XCircle className="w-3.5 h-3.5" />, Review: <Clock className="w-3.5 h-3.5" /> };
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border ${map[decision] ?? 'bg-slate-500/15 text-slate-400 border-slate-500/30'}`}>
      {icons[decision]}{decision}{override && <span className="text-[9px] opacity-70">(Admin)</span>}
    </span>
  );
}

function HistoryCard({ app, index }) {
  const [open, setOpen] = useState(false);
  const d   = app.application_data || {};
  const ts  = app.timestamp ? new Date(app.timestamp).toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';
  const isReview   = app.decision === 'Review';
  const currSymbol = d.currency === 'INR' ? '₹' : '$';
  return (
    <div className={`backdrop-blur-md border rounded-2xl transition-all ${isReview ? 'bg-amber-500/5 border-amber-500/20' : 'bg-white/5 border-white/10 hover:border-white/20'}`}>
      <div className="flex items-center justify-between px-5 py-4 cursor-pointer" onClick={() => setOpen(o => !o)}>
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-slate-500 text-xs font-mono w-5">#{index + 1}</span>
          <Badge decision={app.decision} override={app.admin_override} />
          {app.risk_category && (
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${app.risk_category === 'Low' ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10' : app.risk_category === 'Medium' ? 'text-amber-400 border-amber-500/30 bg-amber-500/10' : 'text-red-400 border-red-500/30 bg-red-500/10'}`}>
              {app.risk_category} Risk
            </span>
          )}
          {isReview && !app.admin_override && <span className="flex items-center gap-1 text-xs text-amber-400 font-semibold"><ShieldAlert className="w-3.5 h-3.5" /> Awaiting admin</span>}
          {app.admin_override && <span className="text-xs text-indigo-400 font-semibold">Verified by Admin</span>}
        </div>
        <div className="flex items-center gap-4">
          <span className="text-slate-500 text-xs hidden sm:block">{ts}</span>
          <span className="text-slate-400 text-sm font-medium">Risk: <span className={(app.risk_score ?? 0) < 0.4 ? 'text-emerald-400' : (app.risk_score ?? 0) < 0.7 ? 'text-amber-400' : 'text-red-400'}>{Math.round((app.risk_score ?? 0) * 100)}%</span></span>
          {open ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
        </div>
      </div>
      {open && (
        <div className="px-5 pb-5 space-y-4 border-t border-white/5 pt-4">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {[
              ['Applicant', d.full_name || d.user_id || '—'],
              ['Monthly Income', d.income ? `${currSymbol}${Number(d.income).toLocaleString()}` : '—'],
              ['Employment', d.employment_type || '—'],
              ['Loan Amount', d.loan_amount ? `${currSymbol}${Number(d.loan_amount).toLocaleString()}` : '—'],
              ['Tenure', d.loan_tenure ? `${d.loan_tenure} mo` : '—'],
              ['Purpose', d.loan_purpose || '—'],
              ['Score', app.internal_score ? `${app.internal_score} (internal)` : '—'],
              ['Confidence', `${Math.round((app.confidence ?? 0) * 100)}%`],
            ].map(([k, v]) => (
              <div key={k} className="bg-slate-900/50 rounded-xl px-3 py-2">
                <p className="text-slate-500 text-xs uppercase tracking-wider mb-0.5">{k}</p>
                <p className="text-white font-semibold text-sm truncate">{v}</p>
              </div>
            ))}
          </div>
          {d.cross_verify_status && d.cross_verify_status !== 'pending' && (
            <div className={`flex items-start gap-2.5 rounded-xl px-4 py-3 border text-xs ${d.cross_verify_status === 'verified' ? 'bg-emerald-500/8 border-emerald-500/25 text-emerald-400' : d.cross_verify_status === 'mismatch' ? 'bg-red-500/8 border-red-500/25 text-red-400' : d.cross_verify_status === 'manual_review' ? 'bg-amber-500/8 border-amber-500/25 text-amber-400' : 'bg-slate-500/8 border-slate-500/25 text-slate-400'}`}>
              <ScanLine className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold uppercase tracking-wider text-[10px] mb-0.5">Cross-Document Verification</p>
                <p className="capitalize">{d.cross_verify_status.replace(/_/g, ' ')}</p>
                {d.cross_verify_flags?.length > 0 && <ul className="mt-1 space-y-0.5">{d.cross_verify_flags.map((f, i) => <li key={i} className="flex items-start gap-1"><span>•</span>{f}</li>)}</ul>}
              </div>
            </div>
          )}
          <div className="bg-slate-900/50 border border-white/5 rounded-xl p-4">
            <p className="text-slate-500 text-xs uppercase tracking-wider mb-1">AI Explanation</p>
            <p className="text-slate-300 text-sm leading-relaxed">{app.explanation || '—'}</p>
          </div>
          {app.fraud_flags?.length > 0 && (
            <div className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-4">
              <p className="text-amber-400 text-xs uppercase tracking-wider mb-2 font-bold">Anomaly Signals Detected</p>
              <ul className="space-y-1">{app.fraud_flags.map((f, i) => <li key={i} className="text-amber-300/80 text-xs flex items-start gap-1.5"><span className="text-amber-400 mt-0.5">•</span>{f}</li>)}</ul>
            </div>
          )}
          {app.admin_note && (
            <div className="bg-indigo-500/5 border border-indigo-500/20 rounded-xl p-4">
              <p className="text-indigo-400 text-xs uppercase tracking-wider mb-1 font-bold">Admin Note</p>
              <p className="text-slate-300 text-sm">{app.admin_note}</p>
            </div>
          )}
          {isReview && !app.admin_override && (
            <div className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-4 flex items-start gap-3">
              <Clock className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
              <p className="text-amber-300 text-sm">Your application is under manual review. An admin will verify your details before making a final decision.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────
//  Main Dashboard
// ─────────────────────────────────────────────────────────
export default function Dashboard() {
  const { user, logout } = useAuth();

  // ── Routing ──────────────────────────────────────────
  // step: 0=KYC 1=Personal 2=Income 3=Loan 4=Result  |  'history'
  const [step,        setStep]        = useState('loading');
  const [history,     setHistory]     = useState([]);
  const [histLoading, setHistLoading] = useState(false);
  const [histRefresh, setHistRefresh] = useState(false);

  // ── KYC ──────────────────────────────────────────────
  const [kycName,     setKycName]     = useState('');

  // ── Form state (all steps share this) ────────────────
  const [form, setForm] = useState({
    full_name: '', age: '', contact: '',
    currency: 'INR', income: '',
    employment_type: 'salaried', employment_length: '',
    loan_amount: '', loan_tenure: '', loan_purpose: 'personal', existing_emi: '',
  });

  // ── Payslip / income verification ────────────────────
  const [payslipFile,      setPayslipFile]      = useState(null);
  const [verifyStatus,     setVerifyStatus]     = useState(null);
  const [verifyData,       setVerifyData]       = useState(null);
  const [nameCheckResult,  setNameCheckResult]  = useState(null);
  const [incomeError,      setIncomeError]      = useState('');
  const fileRef = React.useRef();

  // ── Loan submission ───────────────────────────────────
  const [submitting,  setSubmitting]  = useState(false);
  const [result,      setResult]      = useState(null);
  const [submitError, setSubmitError] = useState('');

  const userId = user?.user_id || user?.email || user?.name;

  // ─────────────────────────────────────────────────────
  //  History fetch
  // ─────────────────────────────────────────────────────
  const fetchHistory = useCallback(async (spin = false) => {
    if (!userId) return [];
    spin ? setHistRefresh(true) : setHistLoading(true);
    try {
      const res = await api.get(`/my-applications?user_id=${encodeURIComponent(userId)}`);
      setHistory(res.data);
      return res.data;
    } catch { return []; }
    finally { setHistLoading(false); setHistRefresh(false); }
  }, [userId]);

  useEffect(() => {
    (async () => {
      const data = await fetchHistory();
      setStep(data?.length > 0 ? 'history' : 0);
    })();
  }, [fetchHistory]);

  // ─────────────────────────────────────────────────────
  //  Handlers
  // ─────────────────────────────────────────────────────
  const handle = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
  };

  const handleKycVerified = (kycResult) => {
    if (kycResult?.name) {
      setKycName(kycResult.name);
      setForm(prev => ({ ...prev, full_name: kycResult.name }));
    }
    setStep(1);
  };

  const handlePayslipSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const ok = ['application/pdf','image/jpeg','image/jpg','image/png'].includes(file.type) || /\.(pdf|jpg|jpeg|png)$/i.test(file.name);
    if (!ok) { setIncomeError('Please upload PDF, JPG, or PNG.'); return; }
    setPayslipFile(file);
    setVerifyStatus(null); setVerifyData(null); setNameCheckResult(null); setIncomeError('');
  };
  const removePayslip = () => {
    setPayslipFile(null); setVerifyStatus(null); setVerifyData(null);
    setNameCheckResult(null); setIncomeError('');
    if (fileRef.current) fileRef.current.value = '';
  };

  const verifyPayslip = async () => {
    if (!payslipFile) { setIncomeError('Please upload your payslip first.'); return false; }
    setVerifyStatus('verifying'); setIncomeError('');
    try {
      const fd = new FormData();
      fd.append('claimed_income', form.income);
      fd.append('document', payslipFile);
      const nameToCheck = kycName || form.full_name;
      if (nameToCheck) fd.append('registered_name', nameToCheck);
      const res  = await fetch('http://localhost:8000/verify-income', { method: 'POST', body: fd });
      const data = await res.json();
      setVerifyData(data.verification_data);
      setNameCheckResult(data.name_check);
      if (data.name_check?.status === 'mismatch') {
        setIncomeError(data.name_check.message || 'Payslip name does not match your registered name.');
        setVerifyStatus('warn'); return false;
      }
      if (data.fraud_flag) {
        setIncomeError(data.message); setVerifyStatus('warn'); return false;
      }
      setVerifyStatus('ok'); return true;
    } catch {
      setIncomeError('Could not reach verification service. Check your connection.');
      setVerifyStatus('warn'); return false;
    }
  };

  const handleSubmitLoan = async () => {
    setSubmitting(true); setSubmitError('');
    const ok = await verifyPayslip();
    if (!ok) { setSubmitting(false); return; }
    const payload = {
      user_id:           userId,
      full_name:         form.full_name,
      age:               form.age ? parseInt(form.age, 10) : undefined,
      contact:           form.contact,
      currency:          form.currency,
      income:            parseFloat(form.income),
      employment_type:   form.employment_type,
      employment_length: form.employment_length ? parseFloat(form.employment_length) : undefined,
      loan_amount:       form.loan_amount ? parseFloat(form.loan_amount) : undefined,
      loan_tenure:       form.loan_tenure ? parseInt(form.loan_tenure, 10) : undefined,
      loan_purpose:      form.loan_purpose,
      existing_emi:      form.existing_emi ? parseFloat(form.existing_emi) : 0,
      payslip_verification: verifyData,
    };
    try {
      const response = await api.post('/analyze-loan-complete', payload);
      setResult(response.data);
      setStep(4);
      setTimeout(() => fetchHistory(true), 1500);
    } catch (err) {
      setSubmitError(err.response?.data?.detail || 'Submission failed. Please try again.');
    } finally { setSubmitting(false); }
  };

  const startNewApplication = () => {
    setStep(0); setKycName(''); setResult(null); setSubmitError('');
    setForm({ full_name:'', age:'', contact:'', currency:'INR', income:'', employment_type:'salaried', employment_length:'', loan_amount:'', loan_tenure:'', loan_purpose:'personal', existing_emi:'' });
    removePayslip();
  };

  const currSymbol = form.currency === 'INR' ? '₹' : '$';
  const pendingReview = history.filter(a => a.decision === 'Review' && !a.admin_override).length;

  // ─────────────────────────────────────────────────────
  //  Shared top bar
  // ─────────────────────────────────────────────────────
  const TopBar = () => (
    <div className="flex items-center justify-between mb-8 border-b border-white/10 pb-5">
      <div>
        <h1 className="text-lg font-black text-white">AI Loan Underwriting</h1>
        <p className="text-slate-500 text-xs mt-0.5">Welcome, <span className="text-amber-400">{user?.name}</span></p>
      </div>
      <div className="flex items-center gap-3">
        {pendingReview > 0 && (
          <span className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs font-semibold animate-pulse">
            <Clock className="w-3.5 h-3.5" /> {pendingReview} Review
          </span>
        )}
        {step !== 'history' && step !== 'loading' && (
          <button onClick={() => setStep('history')} className="text-xs text-slate-400 hover:text-white border border-white/10 px-3 py-1.5 rounded-lg hover:bg-white/5 transition-all flex items-center gap-1.5">
            <History className="w-3.5 h-3.5" /> History
          </button>
        )}
        <button onClick={logout} className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-red-400 border border-white/10 px-3 py-1.5 rounded-lg hover:bg-red-500/10 transition-all">
          <LogOut className="w-3.5 h-3.5" /> Exit
        </button>
      </div>
    </div>
  );

  // ─────────────────────────────────────────────────────
  //  Action button
  // ─────────────────────────────────────────────────────
  const NextBtn = ({ onClick, disabled, children, type = 'button', loading = false }) => (
    <button type={type} onClick={onClick} disabled={disabled || loading}
      className="w-full bg-gradient-to-r from-amber-400 to-amber-600 hover:from-amber-300 hover:to-amber-500 text-slate-900 font-black py-4 rounded-2xl text-base uppercase tracking-widest flex items-center justify-center gap-2 shadow-lg shadow-amber-500/20 transition-all hover:scale-[1.01] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100">
      {loading ? <><Loader2 className="w-5 h-5 animate-spin" /> Processing…</> : children}
    </button>
  );

  const BackBtn = ({ onClick }) => (
    <button type="button" onClick={onClick}
      className="flex items-center gap-2 text-slate-400 hover:text-white text-sm font-semibold mb-6 transition-colors">
      <ArrowLeft className="w-4 h-4" /> Back
    </button>
  );

  // ─────────────────────────────────────────────────────
  //  LOADING
  // ─────────────────────────────────────────────────────
  if (step === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex items-center gap-3">
          <svg className="animate-spin h-7 w-7 text-amber-400" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <p className="text-slate-400">Loading…</p>
        </div>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────
  //  HISTORY
  // ─────────────────────────────────────────────────────
  if (step === 'history') {
    return (
      <div className="min-h-screen px-6 py-8 max-w-5xl mx-auto">
        <TopBar />
        <div className="bg-gradient-to-r from-amber-500/10 to-transparent border border-amber-500/20 rounded-3xl p-8 mb-8 flex flex-col sm:flex-row items-center justify-between gap-6">
          <div>
            <h2 className="text-2xl font-black text-white mb-1">Apply for a New Loan</h2>
            <p className="text-slate-400 text-sm">Complete KYC and get an instant AI-powered decision.</p>
          </div>
          <button onClick={startNewApplication}
            className="flex items-center gap-2 bg-gradient-to-r from-amber-400 to-amber-600 hover:from-amber-300 hover:to-amber-500 text-slate-900 font-black px-8 py-4 rounded-2xl shadow-lg shadow-amber-500/20 transition-all hover:scale-[1.02] uppercase tracking-widest text-sm shrink-0">
            <PlusCircle className="w-5 h-5" /> New Application
          </button>
        </div>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-black text-white flex items-center gap-2">
            <History className="w-5 h-5 text-amber-400" /> My Applications
            {history.length > 0 && <span className="text-sm font-normal text-slate-500">({history.length})</span>}
          </h2>
          <button onClick={() => fetchHistory(true)} disabled={histRefresh}
            className="flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-white px-3 py-1.5 rounded-lg border border-white/10 hover:bg-white/5 transition-all disabled:opacity-50">
            <RefreshCcw className={`w-3.5 h-3.5 ${histRefresh ? 'animate-spin' : ''}`} /> Refresh
          </button>
        </div>
        {histLoading ? (
          <div className="flex items-center justify-center py-12 gap-3">
            <svg className="animate-spin h-6 w-6 text-amber-400" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></svg>
            <p className="text-slate-500 text-sm">Loading…</p>
          </div>
        ) : history.length === 0 ? (
          <div className="bg-white/5 border border-white/10 rounded-2xl p-12 text-center text-slate-500">
            <History className="w-8 h-8 mx-auto mb-3 opacity-50" />
            <p className="font-semibold">No applications yet</p>
            <p className="text-sm mt-1">Click "New Application" to get started.</p>
          </div>
        ) : (
          <div className="space-y-3">{history.map((app, i) => <HistoryCard key={app._id ?? i} app={app} index={i} />)}</div>
        )}
      </div>
    );
  }

  // ─────────────────────────────────────────────────────
  //  STEP 0 — KYC
  // ─────────────────────────────────────────────────────
  if (step === 0) {
    return (
      <div className="min-h-screen px-6 py-8 max-w-2xl mx-auto">
        <TopBar />
        {history.length > 0 && <BackBtn onClick={() => setStep('history')} />}
        <StepBar current={0} />
        <SectionTitle step={1} total={4} title="KYC Verification" subtitle="Verify your identity before applying. Upload your ID card and take a selfie." />
        <CollegeKYC userId={userId} onVerified={handleKycVerified} />
      </div>
    );
  }

  // ─────────────────────────────────────────────────────
  //  STEP 1 — Personal Information
  // ─────────────────────────────────────────────────────
  if (step === 1) {
    const canNext = form.full_name.trim() && form.age && parseInt(form.age) >= 18 && parseInt(form.age) <= 80;
    return (
      <div className="min-h-screen px-6 py-8 max-w-2xl mx-auto">
        <TopBar />
        <BackBtn onClick={() => setStep(0)} />
        <StepBar current={1} />
        <SectionTitle step={2} total={4} title="Personal Information" subtitle="Tell us about yourself. This information is kept confidential." />

        <div className="space-y-5">
          <div>
            <Label icon={User} required>Full Name</Label>
            <Input name="full_name" value={form.full_name} onChange={handle}
              placeholder="As on your ID document" />
            {kycName && form.full_name === kycName && (
              <p className="text-emerald-400 text-xs mt-1.5 flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5" /> Auto-filled from your KYC document
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label icon={User} required>Age</Label>
              <Input name="age" type="number" min="18" max="80" value={form.age} onChange={handle} placeholder="e.g. 28" />
            </div>
            <div>
              <Label icon={Phone}>Contact</Label>
              <Input name="contact" type="text" value={form.contact} onChange={handle} placeholder="Email or Phone" />
            </div>
          </div>
        </div>

        <div className="mt-10">
          <NextBtn onClick={() => setStep(2)} disabled={!canNext}>
            Continue to Income Details <ChevronRight className="w-5 h-5" />
          </NextBtn>
        </div>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────
  //  STEP 2 — Income Information
  // ─────────────────────────────────────────────────────
  if (step === 2) {
    const canNext = form.income && parseFloat(form.income) > 0 && form.employment_type;
    return (
      <div className="min-h-screen px-6 py-8 max-w-2xl mx-auto">
        <TopBar />
        <BackBtn onClick={() => setStep(1)} />
        <StepBar current={2} />
        <SectionTitle step={3} total={4} title="Income Information" subtitle="Your income details help us assess your repayment capacity." />

        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Currency</Label>
              <Select name="currency" value={form.currency} onChange={handle}>
                <option value="INR">INR (₹)</option>
                <option value="USD">USD ($)</option>
              </Select>
            </div>
            <div>
              <Label icon={DollarSign} required>Monthly Income ({currSymbol})</Label>
              <Input name="income" type="number" min="1000" value={form.income} onChange={handle}
                placeholder={form.currency === 'INR' ? '50,000' : '5,000'} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label icon={Briefcase} required>Employment Type</Label>
              <Select name="employment_type" value={form.employment_type} onChange={handle}>
                {EMPLOYMENT_TYPES.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </Select>
            </div>
            <div>
              <Label icon={Briefcase}>Years at Job</Label>
              <Input name="employment_length" type="number" min="0" max="50" step="0.5"
                value={form.employment_length} onChange={handle} placeholder="e.g. 3" />
              <p className="text-xs text-slate-500 mt-1">Enter 0 if new or not applicable</p>
            </div>
          </div>

          {/* Payslip upload */}
          <div>
            <Label icon={FileText} required>Payslip / Salary Slip</Label>
            <input ref={fileRef} type="file" accept=".pdf,.jpg,.jpeg,.png,image/*,application/pdf"
              onChange={handlePayslipSelect} className="hidden" id="payslip-upload" />

            {!payslipFile ? (
              <label htmlFor="payslip-upload"
                className="flex flex-col items-center gap-3 border-2 border-dashed border-white/15 rounded-2xl p-8 cursor-pointer hover:border-amber-500/40 hover:bg-white/5 transition-all">
                <Upload className="w-8 h-8 text-slate-500" />
                <div className="text-center">
                  <p className="text-white font-semibold text-sm">Click to upload payslip</p>
                  <p className="text-slate-500 text-xs mt-1">PDF, JPG, PNG — max 10 MB</p>
                </div>
              </label>
            ) : (
              <div className={`flex items-center gap-3 border rounded-2xl p-4 transition-all ${verifyStatus === 'ok' ? 'bg-emerald-500/5 border-emerald-500/30' : verifyStatus === 'warn' ? 'bg-red-500/5 border-red-500/30' : 'bg-slate-800/60 border-white/10'}`}>
                <FileText className={`w-5 h-5 shrink-0 ${verifyStatus === 'ok' ? 'text-emerald-400' : verifyStatus === 'warn' ? 'text-red-400' : 'text-slate-400'}`} />
                <div className="flex-1 min-w-0">
                  <p className="text-white text-sm font-medium truncate">{payslipFile.name}</p>
                  <p className="text-slate-500 text-xs">{(payslipFile.size / 1024).toFixed(0)} KB</p>
                </div>
                {verifyStatus === 'ok' && <span className="flex items-center gap-1 text-xs text-emerald-400 font-semibold shrink-0"><CheckCircle2 className="w-4 h-4" /> Verified</span>}
                <button type="button" onClick={removePayslip} className="text-slate-500 hover:text-red-400 transition-colors p-1"><X className="w-4 h-4" /></button>
              </div>
            )}

            {incomeError && (
              <div className="mt-3 bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                <p className="text-red-300 text-sm">{incomeError}</p>
              </div>
            )}

            {nameCheckResult && nameCheckResult.status !== 'mismatch' && (
              <div className={`mt-2 flex items-start gap-2 border rounded-xl px-3 py-2.5 text-xs ${nameCheckResult.status === 'verified' ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'bg-amber-500/10 border-amber-500/30 text-amber-400'}`}>
                <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
                <p>{nameCheckResult.message}</p>
              </div>
            )}
          </div>
        </div>

        <div className="mt-10">
          <NextBtn onClick={() => setStep(3)} disabled={!canNext || !payslipFile}>
            Continue to Loan Details <ChevronRight className="w-5 h-5" />
          </NextBtn>
        </div>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────
  //  STEP 3 — Loan Information
  // ─────────────────────────────────────────────────────
  if (step === 3) {
    const canSubmit = form.loan_amount && parseFloat(form.loan_amount) > 0
                   && form.loan_tenure && parseInt(form.loan_tenure) >= 3
                   && form.loan_purpose;
    return (
      <div className="min-h-screen px-6 py-8 max-w-2xl mx-auto">
        <TopBar />
        <BackBtn onClick={() => setStep(2)} />
        <StepBar current={3} />
        <SectionTitle step={4} total={4} title="Loan Details" subtitle="Enter the loan amount and purpose. Our AI will assess your application instantly." />

        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label icon={CreditCard} required>Loan Amount ({currSymbol})</Label>
              <Input name="loan_amount" type="number" min="1000" value={form.loan_amount} onChange={handle}
                placeholder={form.currency === 'INR' ? '5,00,000' : '25,000'} />
            </div>
            <div>
              <Label icon={Calendar} required>Tenure (Months)</Label>
              <Input name="loan_tenure" type="number" min="3" max="360" value={form.loan_tenure} onChange={handle} placeholder="e.g. 36" />
              <p className="text-xs text-slate-500 mt-1">e.g. 12, 24, 36, 60, 120</p>
            </div>
          </div>

          <div>
            <Label icon={FileText} required>Loan Purpose</Label>
            <Select name="loan_purpose" value={form.loan_purpose} onChange={handle}>
              {LOAN_PURPOSES.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </Select>
          </div>

          <div>
            <Label icon={CreditCard}>Existing Monthly EMI ({currSymbol})</Label>
            <Input name="existing_emi" type="number" min="0" value={form.existing_emi} onChange={handle} placeholder="0" />
            <p className="text-xs text-slate-500 mt-1">Total of all current loan repayments. Enter 0 if none.</p>
          </div>

          {/* Summary */}
          <div className="bg-slate-800/40 border border-white/8 rounded-2xl p-5 space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Application Summary</p>
            {[
              ['Applicant',    form.full_name || '—'],
              ['Monthly Income', form.income ? `${currSymbol}${Number(form.income).toLocaleString()}` : '—'],
              ['Employment',   form.employment_type],
              ['Loan Amount',  form.loan_amount ? `${currSymbol}${Number(form.loan_amount).toLocaleString()}` : '—'],
              ['Tenure',       form.loan_tenure ? `${form.loan_tenure} months` : '—'],
              ['Purpose',      LOAN_PURPOSES.find(p => p.value === form.loan_purpose)?.label || '—'],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between text-sm">
                <span className="text-slate-400">{k}</span>
                <span className="text-white font-semibold">{v}</span>
              </div>
            ))}
          </div>

          <div className="bg-amber-500/5 border border-amber-500/20 rounded-xl px-4 py-3 flex items-start gap-2">
            <Info className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <p className="text-amber-300/80 text-xs leading-relaxed">
              Credit score and bureau data are fetched automatically. You don't need to provide them.
            </p>
          </div>

          {submitError && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
              <p className="text-red-300 text-sm">{submitError}</p>
            </div>
          )}
        </div>

        <div className="mt-10">
          <NextBtn onClick={handleSubmitLoan} disabled={!canSubmit} loading={submitting}>
            <Zap className="w-5 h-5" /> Submit Application
          </NextBtn>
        </div>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────
  //  STEP 4 — Result
  // ─────────────────────────────────────────────────────
  if (step === 4) {
    return (
      <div className="min-h-screen px-6 py-8 max-w-3xl mx-auto">
        <TopBar />
        <StepBar current={4} />
        <SectionTitle step={5} total={4} title="Application Result" subtitle="Our AI has analysed your application. Here is your decision." />
        {result && <ResultCard result={result} applicationData={{ ...form, user_id: userId }} />}
        <div className="mt-6 grid grid-cols-2 gap-4">
          <button onClick={() => setStep('history')}
            className="flex items-center justify-center gap-2 bg-white/5 border border-white/10 hover:bg-white/10 text-slate-300 font-semibold py-4 rounded-2xl transition-all text-sm">
            <History className="w-4 h-4 text-amber-400" /> View History
          </button>
          <button onClick={startNewApplication}
            className="flex items-center justify-center gap-2 bg-amber-500/10 border border-amber-500/30 hover:bg-amber-500/20 text-amber-400 font-semibold py-4 rounded-2xl transition-all text-sm">
            <PlusCircle className="w-4 h-4" /> New Application
          </button>
        </div>
      </div>
    );
  }

  return null;
}
