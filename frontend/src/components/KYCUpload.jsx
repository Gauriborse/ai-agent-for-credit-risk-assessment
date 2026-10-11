import React, { useState, useRef } from 'react';
import { Upload, CheckCircle, AlertCircle, X, ShieldCheck, ScanLine, User, Calendar } from 'lucide-react';
import api from '../services/api';

export default function KYCUpload({ userId, onVerified }) {
  const [file,       setFile]       = useState(null);
  const [preview,    setPreview]    = useState(null);
  const [status,     setStatus]     = useState('idle'); // idle | uploading | success | error
  const [result,     setResult]     = useState(null);
  const [errorMsg,   setErrorMsg]   = useState('');
  const fileInputRef = useRef(null);

  const handleFileSelect = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    if (!f.type.startsWith('image/')) {
      setErrorMsg('Please upload an image file (JPG, PNG).');
      return;
    }
    if (f.size > 5 * 1024 * 1024) {
      setErrorMsg('File must be under 5MB.');
      return;
    }
    setFile(f);
    setErrorMsg('');
    setStatus('idle');
    setResult(null);
    const reader = new FileReader();
    reader.onloadend = () => setPreview(reader.result);
    reader.readAsDataURL(f);
  };

  const handleVerify = async () => {
    if (!file) return;
    setStatus('uploading');
    setErrorMsg('');
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('user_id', userId);
      const res = await api.post('/kyc/upload-document', form, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setResult(res.data.verification);
      setStatus('success');
      onVerified(res.data.verification);
    } catch (err) {
      setStatus('error');
      setErrorMsg(err.response?.data?.detail || 'Verification failed. Please try again.');
    }
  };

  const handleClear = () => {
    setFile(null); setPreview(null);
    setStatus('idle'); setResult(null); setErrorMsg('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-3xl shadow-2xl p-8 flex flex-col gap-6">

      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-5">
        <div className="flex items-center gap-3">
          <div className="bg-amber-500/15 p-2 rounded-xl border border-amber-500/30">
            <ScanLine className="w-5 h-5 text-amber-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white tracking-wide">KYC Verification</h2>
            <p className="text-slate-500 text-xs mt-0.5">Upload a government-issued photo ID</p>
          </div>
        </div>
        {status === 'success' && (
          <span className="flex items-center gap-1.5 text-emerald-400 text-sm font-bold">
            <CheckCircle className="w-4 h-4" /> Verified
          </span>
        )}
      </div>

      {/* Drop zone or preview */}
      {!preview ? (
        <div
          onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed border-white/15 rounded-2xl p-12 text-center cursor-pointer hover:border-amber-500/40 hover:bg-white/5 transition-all duration-300 group"
        >
          <div className="relative mx-auto w-fit mb-4">
            <div className="absolute inset-0 bg-amber-500/20 blur-xl rounded-full opacity-0 group-hover:opacity-100 transition-opacity" />
            <div className="relative bg-slate-900 border border-white/10 p-4 rounded-2xl">
              <Upload className="w-8 h-8 text-slate-400 group-hover:text-amber-400 transition-colors" />
            </div>
          </div>
          <p className="text-white font-semibold mb-1">Click to upload ID document</p>
          <p className="text-slate-500 text-sm">Passport, Aadhaar, Driver's License, PAN Card</p>
          <p className="text-slate-600 text-xs mt-2">JPG, PNG · Max 5MB</p>
          <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileSelect} className="hidden" />
        </div>
      ) : (
        <div className="space-y-4">
          {/* Image preview */}
          <div className="relative rounded-2xl overflow-hidden border border-white/10">
            <img src={preview} alt="ID Preview" className="w-full h-52 object-contain bg-slate-900/80" />
            {status !== 'success' && (
              <button onClick={handleClear} className="absolute top-2 right-2 p-1.5 bg-red-500/80 hover:bg-red-500 rounded-lg transition-colors">
                <X className="w-4 h-4 text-white" />
              </button>
            )}
          </div>

          <p className="text-slate-400 text-sm flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-amber-400" />
            {file?.name} &nbsp;·&nbsp; {(file?.size / 1024).toFixed(0)} KB
          </p>
        </div>
      )}

      {/* Error */}
      {errorMsg && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3 flex items-center gap-2 text-red-400 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" /> {errorMsg}
        </div>
      )}

      {/* Verify button */}
      {file && status === 'idle' && (
        <button
          onClick={handleVerify}
          className="bg-gradient-to-r from-amber-400 to-amber-600 hover:from-amber-300 hover:to-amber-500 text-slate-950 font-bold py-4 rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-amber-500/25 transition-all hover:scale-[1.02] uppercase tracking-widest text-sm"
        >
          <ScanLine className="w-4 h-4" /> Verify Identity
        </button>
      )}

      {/* Uploading */}
      {status === 'uploading' && (
        <div className="flex items-center justify-center gap-3 py-3 text-amber-400">
          <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <span className="font-semibold">Scanning document…</span>
        </div>
      )}

      {/* Success result */}
      {status === 'success' && result && (
        <div className="bg-emerald-500/8 border border-emerald-500/25 rounded-2xl p-5 space-y-3">
          <div className="flex items-center gap-2 text-emerald-400 font-bold">
            <CheckCircle className="w-5 h-5" /> Identity Verified
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-slate-900/50 rounded-xl px-3 py-2">
              <p className="text-slate-500 text-xs uppercase tracking-wider mb-0.5 flex items-center gap-1">
                <User className="w-3 h-3" /> Name
              </p>
              <p className="text-white font-semibold text-sm">{result.extracted_name || 'Extracted'}</p>
            </div>
            <div className="bg-slate-900/50 rounded-xl px-3 py-2">
              <p className="text-slate-500 text-xs uppercase tracking-wider mb-0.5 flex items-center gap-1">
                <Calendar className="w-3 h-3" /> DOB
              </p>
              <p className="text-white font-semibold text-sm">{result.extracted_dob || 'Extracted'}</p>
            </div>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500">Confidence</span>
            <span className="text-emerald-400 font-bold">{Math.round((result.confidence ?? 0.75) * 100)}%</span>
          </div>
          {result.mock && (
            <p className="text-slate-600 text-xs">* Document accepted. OCR engine running in demo mode.</p>
          )}
        </div>
      )}

      {/* Error state */}
      {status === 'error' && (
        <div className="bg-red-500/8 border border-red-500/25 rounded-2xl p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-red-400 font-bold text-sm mb-1">Verification Failed</p>
            <p className="text-red-300 text-sm">Please upload a clearer image and try again.</p>
            <button onClick={handleClear} className="text-xs text-slate-400 hover:text-white mt-2 underline">Try again</button>
          </div>
        </div>
      )}
    </div>
  );
}
