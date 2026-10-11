import React, { useState, useRef } from 'react';
import {
  ScanLine, Upload, CheckCircle, XCircle, AlertCircle,
  Camera, User, Calendar, CreditCard, X, ChevronRight,
  ShieldCheck, RefreshCcw, ChevronDown, FileText, Info,
  ShieldQuestion, Loader2
} from 'lucide-react';
import api from '../services/api';
import CrossVerifyPanel from './CrossVerifyPanel';

// ─────────────────────────────────────────────────────────
//  ID Type definitions — rules, labels, field config
// ─────────────────────────────────────────────────────────
const ID_TYPES = {
  aadhaar: {
    label:       'Aadhaar Card',
    icon:        '🪪',
    placeholder: 'Enter 12-digit Aadhaar number',
    hint:        'Exactly 12 digits. No letters or special characters.',
    maxLength:   12,
    fieldLabel:  'Aadhaar Number',
    mask:        (v) => v.replace(/\D/g, '').slice(0, 12),   // digits only
    validate:    (v) => {
      const clean = v.replace(/\s/g, '');
      if (!clean) return 'Aadhaar number is required.';
      if (!/^\d+$/.test(clean)) return 'Aadhaar number must contain digits only.';
      if (clean.length !== 12) return `Aadhaar number must be exactly 12 digits. You entered ${clean.length}.`;
      return null;
    },
    displayValue: (v) => {
      // Format as XXXX XXXX XXXX
      const d = v.replace(/\D/g, '');
      return d.replace(/(\d{4})(\d{4})(\d{4})/, '$1 $2 $3').trim();
    },
  },
  pan: {
    label:       'PAN Card',
    icon:        '🗂️',
    placeholder: 'e.g. ABCDE1234F',
    hint:        '5 letters, 4 digits, 1 letter. Will be converted to uppercase.',
    maxLength:   10,
    fieldLabel:  'PAN Number',
    mask:        (v) => v.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 10),
    validate:    (v) => {
      const clean = v.toUpperCase().trim();
      if (!clean) return 'PAN number is required.';
      if (clean.length !== 10) return `PAN must be exactly 10 characters. You entered ${clean.length}.`;
      if (!/^[A-Z]{5}[0-9]{4}[A-Z]{1}$/.test(clean))
        return 'Invalid PAN format. Expected: 5 letters + 4 digits + 1 letter (e.g. ABCDE1234F).';
      return null;
    },
    displayValue: (v) => v.toUpperCase(),
  },
  dl: {
    label:       'Driving Licence',
    icon:        '🚗',
    placeholder: 'e.g. MH0120230012345',
    hint:        'State code (2 letters) + RTO code (2 digits) + year (4 digits) + number (7 digits). Basic format validation only.',
    maxLength:   20,
    fieldLabel:  'Licence Number',
    mask:        (v) => v.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 20),
    validate:    (v) => {
      const clean = v.toUpperCase().replace(/[-\s]/g, '');
      if (!clean) return 'Driving licence number is required.';
      if (clean.length < 9) return 'Driving licence number is too short. Minimum 9 characters.';
      if (clean.length > 20) return 'Driving licence number is too long. Maximum 20 characters.';
      if (!/^[A-Z]{2}/.test(clean))
        return 'Driving licence must start with 2-letter state code (e.g. MH, DL, KA).';
      if (!/^[A-Z]{2}\d/.test(clean))
        return 'State code must be followed by digits (RTO number + year + licence number).';
      return null;  // basic validation only — full validation requires state-level rules
    },
    displayValue: (v) => v.toUpperCase(),
    note: '⚠️ Basic format validation only. Full validation requires state-specific rules.',
  },
};

const INDIAN_STATES = [
  'Andhra Pradesh','Arunachal Pradesh','Assam','Bihar','Chhattisgarh',
  'Goa','Gujarat','Haryana','Himachal Pradesh','Jharkhand','Karnataka',
  'Kerala','Madhya Pradesh','Maharashtra','Manipur','Meghalaya','Mizoram',
  'Nagaland','Odisha','Punjab','Rajasthan','Sikkim','Tamil Nadu','Telangana',
  'Tripura','Uttar Pradesh','Uttarakhand','West Bengal',
  'Delhi','Jammu & Kashmir','Ladakh',
];

// ─────────────────────────────────────────────────────────
//  Mask a sensitive number for display (show only last 4)
// ─────────────────────────────────────────────────────────
function maskId(idType, value) {
  if (!value) return '';
  const clean = value.replace(/\s/g, '');
  if (idType === 'aadhaar') return 'XXXX XXXX ' + clean.slice(-4);
  if (idType === 'pan')     return clean.slice(0, 2) + '***' + clean.slice(-3);
  return clean.slice(0, 2) + '****' + clean.slice(-3);
}

// ─────────────────────────────────────────────────────────
//  Image upload box
// ─────────────────────────────────────────────────────────
function ImageBox({ label, icon: Icon, preview, onSelect, onClear, accept = 'image/*' }) {
  const ref = useRef(null);
  const isImageOnly = !accept.includes('pdf');
  return (
    <div>
      <p className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-1.5">
        <Icon className="w-3.5 h-3.5" /> {label}
      </p>
      {!preview ? (
        <div
          onClick={() => ref.current?.click()}
          className="border-2 border-dashed border-white/15 rounded-xl p-5 text-center cursor-pointer hover:border-amber-500/40 hover:bg-white/5 transition-all group"
        >
          <Upload className="w-5 h-5 text-slate-500 group-hover:text-amber-400 mx-auto mb-2 transition-colors" />
          <p className="text-slate-500 text-xs">Click to upload</p>
          <p className="text-slate-600 text-xs mt-0.5">
            {isImageOnly ? 'JPG or PNG only · max 5 MB' : 'JPG, PNG, PDF · max 5 MB'}
          </p>
          {isImageOnly && (
            <p className="text-amber-600/70 text-[10px] mt-1">⚠ No PDFs — image required for scanning</p>
          )}
          <input ref={ref} type="file" accept={accept} className="hidden"
            onChange={e => { const f = e.target.files[0]; if (f) onSelect(f); }} />
        </div>
      ) : (
        <div className="relative rounded-xl overflow-hidden border border-white/10">
          {preview.startsWith('data:image') ? (
            <img src={preview} alt={label} className="w-full h-32 object-contain bg-slate-900/80" />
          ) : (
            <div className="h-32 bg-slate-900/80 flex flex-col items-center justify-center gap-2">
              <FileText className="w-8 h-8 text-amber-400" />
              <p className="text-slate-400 text-xs">PDF uploaded</p>
            </div>
          )}
          <button onClick={onClear}
            className="absolute top-1.5 right-1.5 p-1 bg-red-500/80 hover:bg-red-500 rounded-lg transition-colors">
            <X className="w-3 h-3 text-white" />
          </button>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────
//  Inline validation error
// ─────────────────────────────────────────────────────────
function FieldError({ msg }) {
  if (!msg) return null;
  return (
    <p className="flex items-center gap-1.5 text-red-400 text-xs mt-1.5 font-medium">
      <XCircle className="w-3.5 h-3.5 shrink-0" /> {msg}
    </p>
  );
}

// ─────────────────────────────────────────────────────────
//  Main CollegeKYC component
// ─────────────────────────────────────────────────────────
export default function CollegeKYC({ userId, onVerified, payslipData = null }) {
  const [step,      setStep]    = useState('form');   // form | scanning | crossverify | result
  const [idType,    setIdType]  = useState('');       // 'aadhaar' | 'pan' | 'dl'
  const [idNumber,  setIdNumber] = useState('');
  const [dlState,   setDlState]  = useState('');
  const [form,      setForm]    = useState({ full_name: '', dob: '' });
  const [errors,    setErrors]  = useState({});       // field-level errors
  const [touched,   setTouched] = useState({});       // which fields were touched

  const [idFile,       setIdFile]    = useState(null);
  const [idPreview,    setIdPreview] = useState(null);
  const [idFileName,   setIdFileName] = useState('');
  const [selfieFile,   setSelfie]    = useState(null);
  const [selfiePreview,setSelPrev]   = useState(null);
  const [result,       setResult]    = useState(null);
  const [crossVerifyResult, setCrossVerifyResult] = useState(null);
  const [crossVerifyErr,    setCrossVerifyErr]    = useState('');
  const [errorMsg,     setErrorMsg]  = useState('');
  const [autoFilling,  setAutoFilling] = useState(false); // scanning ID for auto-fill

  const def = idType ? ID_TYPES[idType] : null;

  // ── Validation ──────────────────────────────────────────
  const validateField = (name, value) => {
    if (name === 'id_number') return def?.validate(value) || null;
    if (name === 'full_name') return value.trim() ? null : 'Full name is required.';
    if (name === 'dob')       return value ? null : 'Date of birth is required.';
    if (name === 'dl_state')  return value ? null : 'State of issue is required.';
    return null;
  };

  const touch = (name) => setTouched(t => ({ ...t, [name]: true }));

  const handleIdTypeChange = (type) => {
    setIdType(type);
    setIdNumber('');
    setDlState('');
    setErrors({});
    setTouched({});
    setIdFile(null);
    setIdPreview(null);
    setIdFileName('');
    setErrorMsg('');
  };

  const handleIdNumberChange = (raw) => {
    const masked = def ? def.mask(raw) : raw;
    setIdNumber(masked);
    if (touched.id_number) {
      setErrors(e => ({ ...e, id_number: validateField('id_number', masked) }));
    }
  };

  const handleField = (e) => {
    const { name, value } = e.target;
    setForm(p => ({ ...p, [name]: value }));
    if (touched[name]) {
      setErrors(e => ({ ...e, [name]: validateField(name, value) }));
    }
  };

  const blurField = (name, value) => {
    touch(name);
    setErrors(e => ({ ...e, [name]: validateField(name, value) }));
  };

  // ── File select ─────────────────────────────────────────
  const selectFile = (file, setFile, setPreview, setName, imageOnly = false) => {
    const allowed = ['image/jpeg','image/jpg','image/png'];
    const allowedWithPdf = [...allowed, 'application/pdf'];
    const permitted = imageOnly ? allowed : allowedWithPdf;
    const isAllowed = permitted.includes(file.type) ||
      (imageOnly
        ? /\.(jpg|jpeg|png)$/i.test(file.name)
        : /\.(jpg|jpeg|png|pdf)$/i.test(file.name));

    if (!isAllowed) {
      setErrorMsg(imageOnly
        ? 'ID card must be a JPG or PNG image. PDFs cannot be scanned for ID number verification.'
        : 'Please upload JPG, PNG, or PDF only.');
      return;
    }
    if (file.size > 5 * 1024 * 1024) { setErrorMsg('File must be under 5 MB.'); return; }
    setErrorMsg('');
    setFile(file);
    if (setName) setName(file.name);
    const r = new FileReader();
    r.onloadend = () => setPreview(r.result);
    r.readAsDataURL(file);
  };

  const clearFile = (setFile, setPreview, setName) => {
    setFile(null); setPreview(null); if (setName) setName('');
  };

  // ── Auto-fill name from ID card via OCR ─────────────────
  const autoFillFromId = async (file) => {
    if (!idType) return; // need id type selected first
    setAutoFilling(true);
    try {
      const fd = new FormData();
      fd.append('id_type', idType);
      fd.append('id_document', file);
      const res = await api.post('/kyc/extract-fields', fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      if (res.data?.success && res.data?.name) {
        setForm(prev => ({ ...prev, full_name: res.data.name }));
        setErrors(e => ({ ...e, full_name: null }));
        setTouched(t => ({ ...t, full_name: true }));
      }
    } catch (_) {
      // Silent — auto-fill is best-effort, user can type manually
    } finally {
      setAutoFilling(false);
    }
  };

  // ── Can submit? ─────────────────────────────────────────
  const canSubmit = (() => {
    if (!idType || !form.full_name || !form.dob) return false;
    if (!idNumber) return false;
    if (def?.validate(idNumber)) return false;
    if (idType === 'dl' && !dlState) return false;
    if (!idFile || !selfieFile) return false;
    return true;
  })();

  // ── Submit ──────────────────────────────────────────────
  const handleVerify = async () => {
    // Force-touch all fields to show errors
    const allTouched = { id_number: true, full_name: true, dob: true, dl_state: idType === 'dl' };
    setTouched(allTouched);
    const newErrors = {
      id_number: validateField('id_number', idNumber),
      full_name: validateField('full_name', form.full_name),
      dob:       validateField('dob', form.dob),
      ...(idType === 'dl' ? { dl_state: validateField('dl_state', dlState) } : {}),
    };
    setErrors(newErrors);
    if (Object.values(newErrors).some(Boolean)) return;

    setErrorMsg('');
    setCrossVerifyResult(null);
    setCrossVerifyErr('');
    setStep('scanning');

    let cvRes = null; // holds cross-verify response, used after the block

    try {
      // ── Step 1: KYC agent verification ──────────────────
      const fd = new FormData();
      fd.append('user_id',    userId);
      fd.append('full_name',  form.full_name);
      fd.append('dob',        form.dob);
      fd.append('college_id', idNumber.replace(/\s/g, '')); // send raw digits
      fd.append('id_type',    idType);
      fd.append('id_card',    idFile);
      fd.append('selfie',     selfieFile);
      if (idType === 'dl') fd.append('dl_state', dlState);

      const res = await api.post('/kyc/verify-college-id', fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setResult(res.data);

      // ── Step 2: Cross-document verification ─────────────
      // Only run for official IDs (aadhaar, pan, dl) — not college
      if (['aadhaar', 'pan', 'dl'].includes(idType)) {
        setStep('crossverify');
        try {
          const cvFd = new FormData();
          cvFd.append('user_id',          userId);
          cvFd.append('registered_name',  form.full_name);
          cvFd.append('id_type',          idType);
          cvFd.append('id_number',        idNumber.replace(/\s/g, ''));
          cvFd.append('id_document',      idFile);
          // Pass selfie for face comparison (DeepFace will be used if available;
          // otherwise marked "Unable to Verify" — never a false pass)
          if (selfieFile) cvFd.append('selfie', selfieFile);
          // Pass payslip data if provided from parent (Dashboard passes it after payslip upload)
          if (payslipData) {
            cvFd.append('payslip_data_json', JSON.stringify(payslipData));
          }

          const cvResponse = await api.post('/kyc/cross-verify', cvFd, {
            headers: { 'Content-Type': 'multipart/form-data' }
          });
          cvRes = cvResponse;
          setCrossVerifyResult(cvResponse.data);
        } catch (cvErr) {
          setCrossVerifyErr(
            cvErr.response?.data?.detail ||
            'Cross-document verification could not complete. This will be reviewed manually.'
          );
        }
      }

      setStep('result');

      // ── Decide whether to allow progression ──
      // Only block on CONFIRMED mismatch — when we can prove details are wrong.
      // unable_to_verify = OCR couldn't read document (PDF, blurry scan) — allow through
      // with a warning flag, don't hard-block the user.
      const cvStatus = cvRes?.data?.overall_status ?? null;
      const isBlocked = cvStatus === 'mismatch';

      if (res.data.status === 'verified' && !isBlocked) {
        onVerified({
          status:           res.data.status,
          confidence:       res.data.confidence,
          checks:           res.data.checks,
          name:             form.full_name,
          dob:              form.dob,
          id_type:          idType,
          id_number_masked: maskId(idType, idNumber),
        });
      }
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Verification failed. Please try again.');
      setStep('form');
    }
  };

  const reset = () => {
    setStep('form');
    setIdType(''); setIdNumber(''); setDlState('');
    setForm({ full_name: '', dob: '' });
    setErrors({}); setTouched({});
    setIdFile(null); setIdPreview(null); setIdFileName('');
    setSelfie(null); setSelPrev(null);
    setResult(null);
    setCrossVerifyResult(null);
    setCrossVerifyErr('');
    setErrorMsg('');
  };

  // ─────────────────────────────────────────────────────────
  //  RENDER
  // ─────────────────────────────────────────────────────────
  return (
    <div className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-3xl shadow-2xl p-8 flex flex-col gap-6">

      {/* ── Header ── */}
      <div className="flex items-center justify-between border-b border-white/10 pb-5">
        <div className="flex items-center gap-3">
          <div className="bg-amber-500/15 p-2 rounded-xl border border-amber-500/30">
            <ScanLine className="w-5 h-5 text-amber-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white tracking-wide">KYC Verification</h2>
            <p className="text-slate-500 text-xs mt-0.5">Identity · Face Match · Liveness</p>
          </div>
        </div>
        {result && (
          <span className={`flex items-center gap-1.5 text-sm font-bold ${
            result.status === 'verified' ? 'text-emerald-400' : 'text-red-400'
          }`}>
            {result.status === 'verified'
              ? <><CheckCircle className="w-4 h-4" /> Verified</>
              : <><XCircle     className="w-4 h-4" /> Failed</>}
          </span>
        )}
      </div>

      {/* ══════════════════════════════════════
          STEP: FORM
      ══════════════════════════════════════ */}
      {step === 'form' && (
        <>
          {/* Personal details */}
          <div className="space-y-4">
            <p className="text-xs font-bold uppercase tracking-wider text-slate-500">Personal Details</p>

            <div>
              <label className="block text-xs font-semibold tracking-wider text-slate-400 mb-2 uppercase flex items-center gap-1.5">
                <User className="w-3.5 h-3.5" /> Full Name <span className="text-red-400">*</span>
                {autoFilling && (
                  <span className="ml-auto flex items-center gap-1 text-amber-400 text-[10px] font-normal normal-case">
                    <Loader2 className="w-3 h-3 animate-spin" /> Scanning ID…
                  </span>
                )}
                {!autoFilling && form.full_name && idFile && (
                  <span className="ml-auto flex items-center gap-1 text-emerald-400 text-[10px] font-normal normal-case">
                    <CheckCircle className="w-3 h-3" /> Auto-filled from ID
                  </span>
                )}
              </label>
              <input name="full_name" value={form.full_name} onChange={handleField}
                onBlur={() => blurField('full_name', form.full_name)}
                placeholder={autoFilling ? 'Scanning your ID card…' : 'As printed on your ID document'}
                disabled={autoFilling}
                className={`w-full bg-slate-900/60 border rounded-xl p-3.5 text-white placeholder-slate-500
                  focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 outline-none transition-all text-sm
                  ${autoFilling ? 'opacity-60 cursor-wait' : ''}
                  ${touched.full_name && errors.full_name ? 'border-red-500/60' : 'border-white/10'}`}
              />
              <FieldError msg={touched.full_name && errors.full_name} />
            </div>

            <div>
              <label className="block text-xs font-semibold tracking-wider text-slate-400 mb-2 uppercase flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5" /> Date of Birth <span className="text-red-400">*</span>
              </label>
              <input name="dob" value={form.dob} onChange={handleField} type="date"
                onBlur={() => blurField('dob', form.dob)}
                className={`w-full bg-slate-900/60 border rounded-xl p-3.5 text-white
                  focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 outline-none transition-all text-sm
                  ${touched.dob && errors.dob ? 'border-red-500/60' : 'border-white/10'}`}
              />
              <FieldError msg={touched.dob && errors.dob} />
            </div>
          </div>

          {/* ── ID Type selector ── */}
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">Identity Proof</p>
            <label className="block text-xs font-semibold tracking-wider text-slate-400 mb-2 uppercase flex items-center gap-1.5">
              <CreditCard className="w-3.5 h-3.5" /> Select Identity Proof <span className="text-red-400">*</span>
            </label>
            <div className="relative">
              <select
                value={idType}
                onChange={e => handleIdTypeChange(e.target.value)}
                className="w-full bg-slate-900/60 border border-white/10 rounded-xl p-3.5 text-white
                  focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 outline-none
                  transition-all appearance-none cursor-pointer"
              >
                <option value="" disabled>-- Choose ID type --</option>
                {Object.entries(ID_TYPES).map(([key, val]) => (
                  <option key={key} value={key}>{val.icon}  {val.label}</option>
                ))}
              </select>
              <ChevronDown className="absolute right-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
            </div>
          </div>

          {/* ── Dynamic ID number field ── */}
          {idType && def && (
            <div className="space-y-3">
              {/* ID number */}
              <div>
                <label className="block text-xs font-semibold tracking-wider text-slate-400 mb-2 uppercase flex items-center gap-1.5">
                  <CreditCard className="w-3.5 h-3.5" /> {def.fieldLabel} <span className="text-red-400">*</span>
                </label>
                <input
                  value={idType === 'aadhaar' ? def.displayValue(idNumber) : idNumber}
                  onChange={e => handleIdNumberChange(e.target.value)}
                  onBlur={() => { touch('id_number'); setErrors(e => ({ ...e, id_number: validateField('id_number', idNumber) })); }}
                  placeholder={def.placeholder}
                  maxLength={idType === 'aadhaar' ? 14 : def.maxLength} // 14 includes spaces
                  className={`w-full bg-slate-900/60 border rounded-xl p-3.5 text-white placeholder-slate-600
                    focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 outline-none
                    transition-all text-sm font-mono tracking-widest
                    ${touched.id_number && errors.id_number ? 'border-red-500/60' : 'border-white/10'}`}
                />
                <FieldError msg={touched.id_number && errors.id_number} />

                {/* Green tick when valid */}
                {idNumber && !errors.id_number && !def.validate(idNumber) && (
                  <p className="flex items-center gap-1.5 text-emerald-400 text-xs mt-1.5 font-medium">
                    <CheckCircle className="w-3.5 h-3.5" />
                    {def.label} number format is valid.
                  </p>
                )}

                <p className="text-slate-600 text-xs mt-1">{def.hint}</p>

                {/* DL extra note */}
                {idType === 'dl' && def.note && (
                  <div className="flex items-start gap-2 mt-2 bg-amber-500/5 border border-amber-500/20 rounded-lg px-3 py-2">
                    <Info className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                    <p className="text-amber-300/80 text-xs">{def.note}</p>
                  </div>
                )}
              </div>

              {/* DL state of issue */}
              {idType === 'dl' && (
                <div>
                  <label className="block text-xs font-semibold tracking-wider text-slate-400 mb-2 uppercase">
                    State of Issue <span className="text-red-400">*</span>
                  </label>
                  <div className="relative">
                    <select
                      value={dlState}
                      onChange={e => { setDlState(e.target.value); touch('dl_state'); setErrors(err => ({ ...err, dl_state: null })); }}
                      onBlur={() => blurField('dl_state', dlState)}
                      className={`w-full bg-slate-900/60 border rounded-xl p-3.5 text-white
                        focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 outline-none
                        transition-all appearance-none
                        ${touched.dl_state && errors.dl_state ? 'border-red-500/60' : 'border-white/10'}`}
                    >
                      <option value="" disabled>-- Select state --</option>
                      {INDIAN_STATES.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                    <ChevronDown className="absolute right-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                  </div>
                  <FieldError msg={touched.dl_state && errors.dl_state} />
                </div>
              )}
            </div>
          )}

          {/* ── Privacy note ── */}
          {idType && (
            <div className="flex items-start gap-2 bg-slate-800/40 border border-white/5 rounded-xl px-4 py-3">
              <ShieldCheck className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <p className="text-slate-500 text-xs leading-relaxed">
                Your {def?.label} number will be masked in all logs and dashboards.
                Format validation alone does not constitute official verification.
                Documents are processed only for identity verification purposes.
              </p>
            </div>
          )}

          {/* ── Document uploads ── */}
          {idType && (
            <div className="space-y-3">
              <p className="text-xs font-bold uppercase tracking-wider text-slate-500">Document Upload</p>
              <div className="grid grid-cols-2 gap-4">
                <ImageBox
                  label={`${def?.label} Photo`}
                  icon={CreditCard}
                  preview={idPreview}
                  onSelect={f => {
                    selectFile(f, setIdFile, setIdPreview, setIdFileName, true);
                    autoFillFromId(f);
                  }}
                  onClear={() => clearFile(setIdFile, setIdPreview, setIdFileName)}
                  accept="image/jpeg,image/jpg,image/png"
                />
                <ImageBox
                  label="Live Selfie"
                  icon={Camera}
                  preview={selfiePreview}
                  onSelect={f => selectFile(f, setSelfie, setSelPrev, null)}
                  onClear={() => clearFile(setSelfie, setSelPrev, null)}
                  accept="image/*"
                />
              </div>
              {idFileName && (
                <p className="text-slate-500 text-xs flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-amber-400" /> {idFileName}
                </p>
              )}
              <p className="text-slate-600 text-xs">
                Selfie must clearly show your face. Look straight at the camera in good lighting.
              </p>
            </div>
          )}

          {/* ── Global error ── */}
          {errorMsg && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3 flex items-center gap-2 text-red-400 text-sm">
              <AlertCircle className="w-4 h-4 shrink-0" /> {errorMsg}
            </div>
          )}

          {/* ── Submit ── */}
          <button
            onClick={handleVerify}
            disabled={!canSubmit}
            className="bg-gradient-to-r from-amber-400 to-amber-600 hover:from-amber-300 hover:to-amber-500
              text-slate-950 font-bold py-4 rounded-xl flex items-center justify-center gap-2
              shadow-lg shadow-amber-500/25 transition-all hover:scale-[1.02]
              uppercase tracking-widest text-sm disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100"
          >
            <ShieldCheck className="w-4 h-4" /> Run KYC Verification
          </button>
        </>
      )}

      {/* ══════════════════════════════════════
          STEP: SCANNING
      ══════════════════════════════════════ */}
      {step === 'scanning' && (
        <div className="flex flex-col items-center justify-center py-12 gap-5">
          <div className="relative">
            <div className="absolute inset-0 bg-amber-500/20 blur-2xl rounded-full" />
            <div className="relative bg-slate-900 border border-white/10 p-6 rounded-2xl">
              <ScanLine className="w-10 h-10 text-amber-400 animate-pulse" />
            </div>
          </div>
          <div className="text-center space-y-1">
            <p className="text-white font-bold text-lg">KYC Agent Running</p>
            <p className="text-slate-400 text-sm">
              Validating {ID_TYPES[idType]?.label}, OCR, face match & liveness…
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-2 mt-2">
            {['ID Format', 'OCR Scan', 'Face Match', 'Liveness'].map((s, i) => (
              <span key={i}
                className="text-xs bg-amber-500/10 border border-amber-500/20 text-amber-400 px-2.5 py-1 rounded-full animate-pulse"
                style={{ animationDelay: `${i * 0.2}s` }}
              >
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════
          STEP: CROSS-VERIFY (intermediate)
      ══════════════════════════════════════ */}
      {step === 'crossverify' && (
        <div className="flex flex-col items-center justify-center py-12 gap-5">
          <div className="relative">
            <div className="absolute inset-0 bg-indigo-500/20 blur-2xl rounded-full" />
            <div className="relative bg-slate-900 border border-white/10 p-6 rounded-2xl">
              <Loader2 className="w-10 h-10 text-indigo-400 animate-spin" />
            </div>
          </div>
          <div className="text-center space-y-1">
            <p className="text-white font-bold text-lg">Cross-Document Verification</p>
            <p className="text-slate-400 text-sm">
              Comparing identity document against registration details…
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-2 mt-2">
            {['Name Match', 'ID Number', 'Photo Check', 'Consistency'].map((s, i) => (
              <span key={i}
                className="text-xs bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 px-2.5 py-1 rounded-full animate-pulse"
                style={{ animationDelay: `${i * 0.15}s` }}
              >
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════
          STEP: RESULT
      ══════════════════════════════════════ */}
      {step === 'result' && result && (
        <div className="space-y-4">

          {/* Status banner */}
          <div className={`rounded-2xl p-4 border flex items-center gap-3 ${
            result.status === 'verified'
              ? 'bg-emerald-500/10 border-emerald-500/25'
              : 'bg-red-500/10 border-red-500/25'
          }`}>
            {result.status === 'verified'
              ? <CheckCircle className="w-6 h-6 text-emerald-400 shrink-0" />
              : <XCircle     className="w-6 h-6 text-red-400 shrink-0" />}
            <div>
              <p className={`font-bold ${result.status === 'verified' ? 'text-emerald-400' : 'text-red-400'}`}>
                {result.status === 'verified' ? 'KYC Verification Passed' : 'KYC Verification Failed'}
              </p>
              <p className="text-slate-400 text-sm mt-0.5">
                {result.status === 'verified'
                  ? `${ID_TYPES[idType]?.label} (${maskId(idType, idNumber)}) verified successfully.`
                  : 'Please fix the issues below and try again.'}
              </p>
            </div>
          </div>

          {/* Passed */}
          {result.status === 'verified' && (
            <div className="grid grid-cols-2 gap-3">
              {[
                ['Name',         form.full_name],
                ['ID Type',      ID_TYPES[idType]?.label],
                ['ID Number',    maskId(idType, idNumber)],
                ['Confidence',   `${Math.round((result.confidence ?? 0.9) * 100)}%`],
              ].map(([k, v]) => (
                <div key={k} className="bg-slate-900/50 rounded-xl px-3 py-2">
                  <p className="text-slate-500 text-xs uppercase tracking-wider mb-0.5">{k}</p>
                  <p className="text-white font-semibold text-sm">{v}</p>
                </div>
              ))}
            </div>
          )}

          {/* Failed — detailed per-check errors */}
          {result.status === 'failed' && (
            <div className="space-y-2">

              {!result.checks?.id_format?.passed && (
                <div className="bg-red-500/8 border border-red-500/20 rounded-xl px-4 py-3 flex items-start gap-2">
                  <XCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-red-400 text-xs font-bold uppercase tracking-wider mb-0.5">
                      Invalid {ID_TYPES[idType]?.label} Number
                    </p>
                    <p className="text-red-300 text-sm">{result.checks.id_format?.detail}</p>
                  </div>
                </div>
              )}

              {result.checks?.face_match && !result.checks.face_match?.passed && (
                <div className="bg-red-500/8 border border-red-500/20 rounded-xl px-4 py-3 flex items-start gap-2">
                  <XCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-red-400 text-xs font-bold uppercase tracking-wider mb-0.5">Face Mismatch</p>
                    <p className="text-red-300 text-sm">
                      {result.checks.face_match?.distance >= 1.0
                        ? 'No face detected. Upload a clear front-facing photo for both ID and selfie.'
                        : `Selfie does not match the face on your ${ID_TYPES[idType]?.label}. Upload photos of the same person.`}
                    </p>
                  </div>
                </div>
              )}

              {result.checks?.liveness && !result.checks.liveness?.passed && (
                <div className="bg-red-500/8 border border-red-500/20 rounded-xl px-4 py-3 flex items-start gap-2">
                  <XCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-red-400 text-xs font-bold uppercase tracking-wider mb-0.5">Selfie Quality Failed</p>
                    <p className="text-red-300 text-sm">
                      Photo is too blurry or low resolution (sharpness: {result.checks.liveness?.sharpness_score}).
                      Take a clear, well-lit selfie.
                    </p>
                  </div>
                </div>
              )}

              {result.checks?.name_match && !result.checks.name_match?.passed && result.checks.name_match?.ocr_mode === 'live' && (
                <div className="bg-amber-500/8 border border-amber-500/20 rounded-xl px-4 py-3 flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-amber-400 text-xs font-bold uppercase tracking-wider mb-0.5">Name Mismatch</p>
                    <p className="text-amber-300 text-sm">
                      You entered <span className="font-bold">{result.checks.name_match?.provided}</span> but ID shows <span className="font-bold">{result.checks.name_match?.extracted || 'unreadable'}</span>.
                      Enter your name exactly as on the ID.
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Simple Cross-Document Check Summary ── */}
          {crossVerifyResult && (() => {
            const cv = crossVerifyResult;
            const checks = cv.checks ?? {};

            // Build a simple list of what passed and what failed
            const issues = [];
            const passed = [];

            // Name check
            if (checks.kyc_name?.status === 'mismatch')
              issues.push('Name on document does not match your registered name.');
            else if (checks.kyc_name?.status === 'verified')
              passed.push('Name matches');

            // ID number check
            if (checks.kyc_id_number?.status === 'mismatch')
              issues.push('ID number does not match the uploaded document.');
            else if (checks.kyc_id_number?.status === 'verified')
              passed.push('ID number matches');

            // Face match
            if (checks.kyc_selfie_match?.status === 'mismatch')
              issues.push('Your selfie does not match the photo on the ID card.');
            else if (checks.kyc_selfie_match?.status === 'verified')
              passed.push('Face matches');

            // Payslip name
            if (checks.payslip_name?.status === 'mismatch')
              issues.push('Payslip name does not match your registered name.');
            else if (checks.payslip_name?.status === 'verified')
              passed.push('Payslip name matches');

            const hasMismatch = cv.overall_status === 'mismatch';
            const isUnable = cv.overall_status === 'unable_to_verify' || cv.overall_status === 'partially_verified';
            const allGood = cv.overall_status === 'verified' || (issues.length === 0 && !hasMismatch);

            return (
              <div className="space-y-2">
                {/* Mismatch — hard block */}
                {hasMismatch && (
                  <div className="bg-red-500/10 border-2 border-red-500/40 rounded-2xl px-4 py-4 space-y-2">
                    <div className="flex items-center gap-2">
                      <XCircle className="w-5 h-5 text-red-400 shrink-0" />
                      <p className="text-red-400 font-bold text-sm">Document Verification Failed</p>
                    </div>
                    <ul className="space-y-1.5">
                      {issues.map((msg, i) => (
                        <li key={i} className="flex items-start gap-2 text-red-300 text-sm">
                          <span className="text-red-400 mt-0.5 shrink-0">✕</span> {msg}
                        </li>
                      ))}
                    </ul>
                    <p className="text-slate-400 text-xs pt-1 border-t border-red-500/20">
                      Please re-upload the correct document and try again.
                    </p>
                  </div>
                )}

                {/* Unable to verify — warn but allow */}
                {!hasMismatch && isUnable && (
                  <div className="bg-amber-500/8 border border-amber-500/30 rounded-2xl px-4 py-3 flex items-start gap-3">
                    <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                    <div>
                      <p className="text-amber-400 font-bold text-sm">Document could not be fully read</p>
                      <p className="text-amber-300/80 text-xs mt-1 leading-relaxed">
                        Your document image could not be scanned automatically (upload a clear JPG instead of PDF for best results).
                        You can still proceed — a staff member will verify your documents manually.
                      </p>
                    </div>
                  </div>
                )}

                {/* All good */}
                {allGood && !hasMismatch && !isUnable && (
                  <div className="bg-emerald-500/8 border border-emerald-500/25 rounded-2xl px-4 py-3 flex items-center gap-3">
                    <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                    <div>
                      <p className="text-emerald-400 font-bold text-sm">Document Verified</p>
                      {passed.length > 0 && (
                        <p className="text-emerald-300/70 text-xs mt-0.5">{passed.join(' · ')}</p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })()}

          {/* Cross-verify error (non-blocking) */}
          {crossVerifyErr && !crossVerifyResult && (
            <div className="bg-amber-500/8 border border-amber-500/20 rounded-xl px-4 py-3 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <p className="text-amber-300/80 text-xs leading-relaxed">
                Document cross-check could not complete. You can still proceed — your documents will be reviewed manually.
              </p>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            {/* KYC agent failed — try again */}
            {result.status !== 'verified' && (
              <button onClick={reset}
                className="flex-1 flex items-center justify-center gap-2 bg-white/5 border border-white/10 hover:bg-white/10 text-white font-bold py-3 rounded-xl transition-all text-sm">
                <RefreshCcw className="w-4 h-4" /> Try Again
              </button>
            )}

            {/* Confirmed mismatch — force re-upload, block proceed */}
            {result.status === 'verified' && crossVerifyResult?.overall_status === 'mismatch' && (
              <button onClick={reset}
                className="flex-1 flex items-center justify-center gap-2 bg-red-500/15 border border-red-500/30 hover:bg-red-500/25 text-red-400 font-bold py-3 rounded-xl transition-all text-sm">
                <RefreshCcw className="w-4 h-4" /> Re-upload Correct Document
              </button>
            )}

            {/* All other cases — allow proceeding */}
            {result.status === 'verified' && crossVerifyResult?.overall_status !== 'mismatch' && (
              <div className="flex-1 flex items-center justify-center gap-2 bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 font-bold py-3 rounded-xl text-sm">
                <CheckCircle className="w-4 h-4" /> Identity Confirmed — Proceed to Loan Form
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
