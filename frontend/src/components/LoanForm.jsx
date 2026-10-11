import React, { useState, useRef } from 'react';
import {
  Zap, RefreshCcw, Upload, AlertTriangle, CheckCircle2,
  User, Phone, Briefcase, DollarSign, Calendar, FileText,
  CreditCard, Loader2, X, AlertCircle, Info, ShieldAlert,
  ShieldCheck, ShieldX, ShieldQuestion
} from 'lucide-react';

const EMPLOYMENT_TYPES = [
  { value: 'salaried',     label: 'Salaried Employee' },
  { value: 'self-employed',label: 'Self Employed' },
  { value: 'business',     label: 'Business Owner' },
  { value: 'student',      label: 'Student' },
  { value: 'unemployed',   label: 'Currently Unemployed' },
];

const LOAN_PURPOSES = [
  { value: 'home',        label: 'Home / Mortgage' },
  { value: 'vehicle',     label: 'Vehicle Purchase' },
  { value: 'education',   label: 'Education' },
  { value: 'medical',     label: 'Medical Emergency' },
  { value: 'business',    label: 'Business / Startup' },
  { value: 'personal',    label: 'Personal Use' },
  { value: 'debt',        label: 'Debt Consolidation' },
  { value: 'other',       label: 'Other' },
];

function Field({ label, required, hint, icon: Icon, children }) {
  return (
    <div>
      <label className="flex items-center gap-1.5 text-xs font-semibold tracking-wider text-slate-400 mb-2 uppercase">
        {Icon && <Icon className="w-3.5 h-3.5" />}
        {label}
        {required && <span className="text-red-400 ml-0.5">*</span>}
      </label>
      {children}
      {hint && <p className="text-xs text-slate-500 mt-1">{hint}</p>}
    </div>
  );
}

function Input({ ...props }) {
  return (
    <input
      className="w-full bg-slate-900/60 border border-white/10 rounded-xl p-3.5 text-white placeholder-slate-600
                 focus:bg-slate-900 focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 outline-none
                 transition-all shadow-inner disabled:opacity-50"
      {...props}
    />
  );
}

function Select({ children, ...props }) {
  return (
    <select
      className="w-full bg-slate-900/60 border border-white/10 rounded-xl p-3.5 text-white
                 focus:bg-slate-900 focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 outline-none
                 transition-all shadow-inner appearance-none"
      {...props}
    >
      {children}
    </select>
  );
}

// ── Payslip name check result badge ───────────────────────
function NameCheckBadge({ nameCheck }) {
  if (!nameCheck) return null;
  const cfg = {
    verified:         { icon: ShieldCheck,   cls: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400', label: 'Name Matched' },
    mismatch:         { icon: ShieldX,       cls: 'bg-red-500/10 border-red-500/30 text-red-400',             label: 'Name Mismatch' },
    unable_to_verify: { icon: ShieldQuestion,cls: 'bg-slate-500/10 border-slate-500/30 text-slate-400',       label: 'Name Unverified' },
    manual_review:    { icon: ShieldAlert,   cls: 'bg-amber-500/10 border-amber-500/30 text-amber-400',       label: 'Manual Review' },
    pending:          { icon: ShieldQuestion,cls: 'bg-slate-500/10 border-slate-500/30 text-slate-400',       label: 'Pending' },
  };
  const s = cfg[nameCheck.status] ?? cfg.pending;
  const Ico = s.icon;
  return (
    <div className={`flex items-start gap-2 border rounded-xl px-3 py-2.5 mt-2 ${s.cls}`}>
      <Ico className="w-4 h-4 shrink-0 mt-0.5" />
      <div>
        <p className="text-xs font-bold">{s.label}</p>
        {nameCheck.message && (
          <p className="text-xs leading-relaxed opacity-80 mt-0.5">{nameCheck.message}</p>
        )}
        {nameCheck.confidence > 0 && (
          <p className="text-[10px] opacity-60 mt-0.5">
            Confidence: {Math.round(nameCheck.confidence * 100)}%
          </p>
        )}
      </div>
    </div>
  );
}

export default function LoanForm({ onSubmit, isLoading, onPayslipVerified, registeredName = '' }) {
  const [form, setForm] = useState({
    full_name:       '',
    age:             '',
    contact:         '',
    currency:        'USD',
    income:          '',
    employment_type: 'salaried',
    employment_length: '',
    loan_amount:     '',
    loan_tenure:     '',
    loan_purpose:    'personal',
    existing_emi:    '',
  });

  const [payslipFile,  setPayslipFile]  = useState(null);
  const [fraudAlert,   setFraudAlert]   = useState(null);
  const [verifyStatus, setVerifyStatus] = useState(null); // null | 'verifying' | 'ok' | 'warn' | 'name_mismatch'
  const [verifyData,   setVerifyData]   = useState(null);
  const [nameMismatch, setNameMismatch] = useState(null); // { status, message }
  const [nameCheckResult, setNameCheckResult] = useState(null); // full name_check from backend
  const fileRef = useRef();

  const handle = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
  };

  const handleFile = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const ok = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png'].includes(file.type)
      || /\.(pdf|jpg|jpeg|png)$/i.test(file.name);
    if (!ok) {
      alert('Please upload a PDF, JPG, or PNG file.');
      e.target.value = '';
      return;
    }
    setPayslipFile(file);
    setFraudAlert(null);
    setVerifyStatus(null);
    setVerifyData(null);
  };

  const removeFile = () => {
    setPayslipFile(null);
    setFraudAlert(null);
    setVerifyStatus(null);
    setVerifyData(null);
    setNameMismatch(null);
    setNameCheckResult(null);
    if (fileRef.current) fileRef.current.value = '';
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFraudAlert(null);

    if (!payslipFile) {
      setFraudAlert('Payment slip is required. Please upload your salary slip or income proof.');
      return;
    }

    // Step 1 — verify payslip
    setVerifyStatus('verifying');
    try {
      const fd = new FormData();
      fd.append('claimed_income', form.income);
      fd.append('document', payslipFile);
      // Pass registered name (from KYC form or loan form) for payslip name cross-check
      const nameToCheck = registeredName || form.full_name;
      if (nameToCheck) fd.append('registered_name', nameToCheck);

      const res = await fetch('http://localhost:8000/verify-income', {
        method: 'POST',
        body: fd,
      });
      const data = await res.json();
      setVerifyData(data.verification_data);

      // Handle payslip name mismatch
      const nc = data.name_check;
      setNameCheckResult(nc);
      if (nc && nc.status === 'mismatch') {
        setNameMismatch(nc);
        setVerifyStatus('name_mismatch');
        setFraudAlert(
          nc.message ||
          'The name on your payslip does not match your registered name. ' +
          'Please upload the correct document or request manual review.'
        );
        return;
      }

      if (data.fraud_flag) {
        setFraudAlert(data.message);
        setVerifyStatus('warn');
        return;
      }
      setVerifyStatus('ok');
    } catch (err) {
      console.error('Income verification error:', err);
      setVerifyStatus('warn');
      setFraudAlert('Could not reach the verification service. Please check your connection and try again.');
      return;
    }

    // Step 2 — submit application
    const payload = {
      user_id:          form.contact || form.full_name || 'applicant',
      full_name:        form.full_name,
      age:              form.age ? parseInt(form.age, 10) : undefined,
      contact:          form.contact,
      currency:         form.currency,
      income:           parseFloat(form.income),
      employment_type:  form.employment_type,
      employment_length: form.employment_length ? parseFloat(form.employment_length) : undefined,
      loan_amount:      form.loan_amount ? parseFloat(form.loan_amount) : undefined,
      loan_tenure:      form.loan_tenure ? parseInt(form.loan_tenure, 10) : undefined,
      loan_purpose:     form.loan_purpose,
      existing_emi:     form.existing_emi ? parseFloat(form.existing_emi) : 0,
      payslip_verification: verifyData,
    };

    onSubmit(payload);
  };

  const reset = () => {
    setForm({
      full_name: '', age: '', contact: '', currency: 'USD', income: '',
      employment_type: 'salaried', employment_length: '', loan_amount: '',
      loan_tenure: '', loan_purpose: 'personal', existing_emi: '',
    });
    removeFile();
  };

  const currSymbol = form.currency === 'INR' ? '₹' : '$';

  return (
    <form
      onSubmit={handleSubmit}
      className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-3xl shadow-2xl p-8 flex flex-col gap-6 hover:border-white/20 transition-all duration-500"
    >
      {/* Header */}
      <div className="flex justify-between items-center border-b border-white/10 pb-5">
        <div>
          <h2 className="text-xl font-bold text-white tracking-wide">Loan Application</h2>
          <p className="text-xs text-slate-500 mt-0.5">Credit info is fetched automatically — no technical fields required</p>
        </div>
        <button
          type="button"
          onClick={reset}
          className="text-xs font-semibold uppercase tracking-wider bg-white/5 border border-white/10 text-slate-300
                     hover:text-white px-4 py-2 rounded-lg transition-all hover:bg-white/10 flex items-center gap-2"
        >
          <RefreshCcw className="w-3.5 h-3.5" /> Reset
        </button>
      </div>

      {/* Fraud / verification alert */}
      {fraudAlert && (
        <div className="bg-red-500/10 border-2 border-red-500/50 rounded-xl p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
          <div>
            <h3 className="text-red-400 font-bold text-sm mb-1">Verification Issue</h3>
            <p className="text-red-300 text-sm leading-relaxed">{fraudAlert}</p>
          </div>
        </div>
      )}

      {/* ── Section 1: Personal Info ── */}
      <div className="space-y-4">
        <p className="text-xs font-bold uppercase tracking-widest text-amber-400/80">Personal Information</p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Full Name" required icon={User}>
            <Input
              required name="full_name" type="text" value={form.full_name}
              onChange={handle} placeholder="e.g. Priya Sharma"
            />
          </Field>
          <Field label="Age" required icon={User} hint="Must be 18–80">
            <Input
              required name="age" type="number" min="18" max="80"
              value={form.age} onChange={handle} placeholder="28"
            />
          </Field>
        </div>

        <Field label="Contact (Phone or Email)" icon={Phone}>
          <Input
            name="contact" type="text" value={form.contact}
            onChange={handle} placeholder="email@example.com or +91-9876543210"
          />
        </Field>
      </div>

      {/* ── Section 2: Income ── */}
      <div className="space-y-4">
        <p className="text-xs font-bold uppercase tracking-widest text-amber-400/80">Income Details</p>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Currency">
            <Select name="currency" value={form.currency} onChange={handle}>
              <option value="USD">USD ($)</option>
              <option value="INR">INR (₹)</option>
            </Select>
          </Field>
          <Field label={`Monthly Income (${currSymbol})`} required icon={DollarSign}>
            <Input
              required name="income" type="number" min="1000"
              value={form.income} onChange={handle}
              placeholder={form.currency === 'INR' ? '50000' : '5000'}
            />
          </Field>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Employment Type" required icon={Briefcase}>
            <Select required name="employment_type" value={form.employment_type} onChange={handle}>
              {EMPLOYMENT_TYPES.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </Select>
          </Field>
          <Field label="Years at Current Job" icon={Briefcase} hint="0 if new / not applicable">
            <Input
              name="employment_length" type="number" min="0" max="50" step="0.5"
              value={form.employment_length} onChange={handle} placeholder="3"
            />
          </Field>
        </div>
      </div>

      {/* ── Section 3: Loan Details ── */}
      <div className="space-y-4">
        <p className="text-xs font-bold uppercase tracking-widest text-amber-400/80">Loan Details</p>

        <div className="grid grid-cols-2 gap-4">
          <Field label={`Loan Amount (${currSymbol})`} required icon={CreditCard}>
            <Input
              required name="loan_amount" type="number" min="1000"
              value={form.loan_amount} onChange={handle}
              placeholder={form.currency === 'INR' ? '500000' : '25000'}
            />
          </Field>
          <Field label="Loan Tenure (Months)" required icon={Calendar} hint="e.g. 12, 24, 36, 60">
            <Input
              required name="loan_tenure" type="number" min="3" max="360"
              value={form.loan_tenure} onChange={handle} placeholder="36"
            />
          </Field>
        </div>

        <Field label="Loan Purpose" required icon={FileText}>
          <Select required name="loan_purpose" value={form.loan_purpose} onChange={handle}>
            {LOAN_PURPOSES.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </Select>
        </Field>

        <Field
          label={`Existing Monthly EMI (${currSymbol})`}
          icon={CreditCard}
          hint="Total of all current loan/credit repayments. Enter 0 if none."
        >
          <Input
            name="existing_emi" type="number" min="0"
            value={form.existing_emi} onChange={handle} placeholder="0"
          />
        </Field>
      </div>

      {/* ── Section 4: Payment Slip Upload ── */}
      <div className="space-y-2">
        <p className="text-xs font-bold uppercase tracking-widest text-amber-400/80 mb-2">Income Proof</p>
        <Field
          label="Payment Slip / Salary Slip"
          required
          hint="Upload your most recent payslip. Accepted: PDF, JPG, PNG (max 10 MB)."
        >
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,image/*,application/pdf"
            onChange={handleFile}
            className="hidden"
            id="payslip-upload"
          />

          {!payslipFile ? (
            <label
              htmlFor="payslip-upload"
              className="w-full bg-slate-900/60 border border-dashed border-white/20 rounded-xl p-6
                         text-slate-400 hover:text-white hover:border-amber-500/50 cursor-pointer
                         flex flex-col items-center gap-2 transition-all hover:bg-slate-900"
            >
              <Upload className="w-6 h-6" />
              <span className="text-sm font-medium">Click to upload payslip</span>
              <span className="text-xs text-slate-600">PDF, JPG, PNG — max 10 MB</span>
            </label>
          ) : (
            <div className={`border rounded-xl p-4 flex items-center gap-3 transition-all ${
              verifyStatus === 'ok'
                ? 'bg-emerald-500/5 border-emerald-500/30'
                : verifyStatus === 'warn'
                ? 'bg-amber-500/5 border-amber-500/30'
                : 'bg-slate-900/60 border-white/10'
            }`}>
              <FileText className={`w-5 h-5 shrink-0 ${
                verifyStatus === 'ok' ? 'text-emerald-400' :
                verifyStatus === 'warn' ? 'text-amber-400' : 'text-slate-400'
              }`} />
              <div className="flex-1 min-w-0">
                <p className="text-white text-sm font-medium truncate">{payslipFile.name}</p>
                <p className="text-slate-500 text-xs">{(payslipFile.size / 1024).toFixed(1)} KB</p>
              </div>
              {verifyStatus === 'ok' && (
                <span className="flex items-center gap-1 text-xs text-emerald-400 font-semibold shrink-0">
                  <CheckCircle2 className="w-4 h-4" /> Verified
                </span>
              )}
              {verifyData?.extracted_employer && (
                <span className="text-xs text-slate-500 hidden sm:block shrink-0">
                  {verifyData.extracted_employer}
                </span>
              )}
              <button
                type="button"
                onClick={removeFile}
                className="text-slate-500 hover:text-red-400 transition-colors shrink-0 p-1"
                title="Remove file"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}
        </Field>

        {/* Name check result (shown after payslip verification) */}
        {nameCheckResult && (
          <NameCheckBadge nameCheck={nameCheckResult} />
        )}
      </div>

      {/* ── Submit ── */}
      <button
        type="submit"
        disabled={isLoading || verifyStatus === 'verifying'}
        className="mt-2 bg-gradient-to-r from-amber-400 to-amber-600 hover:from-amber-300 hover:to-amber-500
                   text-slate-950 font-bold text-base py-4 rounded-xl flex justify-center items-center
                   shadow-lg shadow-amber-500/25 transition-all duration-300 disabled:opacity-50
                   disabled:grayscale hover:scale-[1.02] disabled:hover:scale-100
                   uppercase tracking-widest disabled:cursor-not-allowed"
      >
        {verifyStatus === 'verifying' ? (
          <span className="flex items-center gap-3">
            <Loader2 className="animate-spin h-5 w-5" /> Verifying Payslip…
          </span>
        ) : isLoading ? (
          <span className="flex items-center gap-3">
            <Loader2 className="animate-spin h-5 w-5" /> Analyzing Application…
          </span>
        ) : (
          <span className="flex items-center gap-2">
            <Zap className="w-5 h-5" /> Submit Application
          </span>
        )}
      </button>

      <p className="text-center text-xs text-slate-600 leading-relaxed">
        Credit score and credit history are fetched automatically from our simulated bureau.
        You do not need to provide them.
      </p>
    </form>
  );
}
