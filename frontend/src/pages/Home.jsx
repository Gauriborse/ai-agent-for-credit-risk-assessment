import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, CheckCircle, Users, Award, Lock } from 'lucide-react';

const stats = [
  { value: '99.8%', label: 'Uptime SLA' },
  { value: '<500ms', label: 'Avg Decision Time' },
  { value: '40%', label: 'Risk Reduction' },
  { value: '10x', label: 'Faster Processing' },
];

export default function Home() {
  return (
    <div className="pb-24">

      {/* ── Hero ── */}
      <section className="relative pt-20 pb-28 px-4 max-w-7xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <div>
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-sm font-semibold mb-8 tracking-wide">
              <div className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
              AI-Powered Loan Underwriting
            </div>
            <h1 className="text-5xl md:text-6xl font-black tracking-tight mb-6 leading-tight">
              <span className="text-white">Smarter Capital.</span><br />
              <span className="bg-gradient-to-r from-amber-200 via-amber-400 to-amber-600 bg-clip-text text-transparent">
                Instant Decisions.
              </span>
            </h1>
            <p className="text-slate-400 text-lg leading-relaxed max-w-lg font-light mb-10">
              Advanced AI underwriting that transforms raw financial data into precise, explainable loan decisions — in milliseconds.
            </p>
            <div className="flex flex-col sm:flex-row gap-4">
              <Link to="/signup" className="inline-flex items-center justify-center gap-2 bg-gradient-to-r from-amber-400 to-amber-600 text-slate-950 px-8 py-4 rounded-xl font-bold text-lg shadow-xl shadow-amber-500/25 hover:from-amber-300 hover:to-amber-500 hover:scale-105 transition-all duration-300">
                Get Started Free <ArrowRight className="w-5 h-5" />
              </Link>
              <Link to="/how-it-works" className="inline-flex items-center justify-center gap-2 text-slate-300 border border-white/10 px-8 py-4 rounded-xl font-semibold text-lg hover:border-white/20 hover:bg-white/5 transition-all duration-300">
                How It Works
              </Link>
            </div>
            <div className="flex items-center gap-6 mt-10">
              {[{ icon: Lock, label: 'Enterprise Security' }, { icon: Award, label: 'AI Certified' }, { icon: Users, label: '10K+ Users' }].map(({ icon: Icon, label }) => (
                <div key={label} className="flex items-center gap-2 text-slate-500 text-xs font-semibold">
                  <Icon className="w-3.5 h-3.5 text-amber-400" /> {label}
                </div>
              ))}
            </div>
          </div>

          <div className="relative hidden lg:block">
            {/* Ambient glow behind cards */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-80 h-80 bg-amber-400/20 blur-[80px] rounded-full" />
            <div className="absolute top-1/3 right-10 w-40 h-40 bg-amber-600/15 blur-[60px] rounded-full" />

            {/* Card stack container */}
            <div className="relative flex items-center justify-center h-80">

              {/* Back card — amber gold */}
              <div className="absolute top-4 left-8 w-72 rotate-[-8deg] translate-y-2">
                <div className="relative w-full bg-gradient-to-br from-amber-300 via-amber-500 to-amber-800 rounded-2xl p-5 shadow-2xl shadow-amber-500/40 border border-amber-300/30">
                  <div className="absolute inset-0 rounded-2xl bg-gradient-to-tr from-white/15 via-white/5 to-transparent" />
                  {/* Top row */}
                  <div className="flex items-start justify-between mb-6">
                    <div>
                      <p className="text-amber-950/50 text-[7px] font-bold uppercase tracking-widest">LoanRisk</p>
                      <p className="text-slate-950/80 text-xs font-black">AI Credit</p>
                    </div>
                    {/* Chip */}
                    <div className="w-9 h-7 bg-gradient-to-br from-yellow-100 to-yellow-400 rounded-md border border-yellow-300/60 grid grid-cols-2 gap-0.5 p-1">
                      {[0,1,2,3].map(i => <div key={i} className="bg-yellow-700/30 rounded-sm" />)}
                    </div>
                  </div>
                  {/* Number */}
                  <div className="flex gap-3 mb-4">
                    {['1234', '5678', '9012', '3456'].map((g, i) => (
                      <span key={i} className="text-slate-950/70 text-sm font-mono font-bold tracking-widest">{g}</span>
                    ))}
                  </div>
                  <div className="flex items-end justify-between">
                    <div>
                      <p className="text-amber-950/40 text-[7px] uppercase tracking-widest">Valid Thru</p>
                      <p className="text-slate-950/80 text-xs font-bold">06/25</p>
                    </div>
                    <div className="flex -space-x-2 opacity-60">
                      <div className="w-7 h-7 rounded-full bg-slate-950/40" />
                      <div className="w-7 h-7 rounded-full bg-slate-950/20" />
                    </div>
                  </div>
                </div>
              </div>

              {/* Front card — dark slate */}
              <div className="absolute top-0 right-4 w-72 rotate-[6deg]">
                {/* Glow */}
                <div className="absolute inset-0 bg-amber-400/25 blur-2xl rounded-2xl scale-110" />
                <div className="relative w-full bg-gradient-to-br from-slate-800 via-slate-900 to-slate-950 rounded-2xl p-5 shadow-2xl shadow-slate-900/60 border border-amber-500/20">
                  <div className="absolute inset-0 rounded-2xl bg-gradient-to-tr from-amber-400/5 via-transparent to-transparent" />
                  {/* Top row */}
                  <div className="flex items-start justify-between mb-6">
                    <div>
                      <p className="text-amber-400/60 text-[7px] font-bold uppercase tracking-widest">LoanRisk</p>
                      <p className="text-amber-400 text-xs font-black">AI Credit</p>
                    </div>
                    {/* Chip */}
                    <div className="w-9 h-7 bg-gradient-to-br from-amber-300 to-amber-500 rounded-md border border-amber-400/40 grid grid-cols-2 gap-0.5 p-1">
                      {[0,1,2,3].map(i => <div key={i} className="bg-amber-800/40 rounded-sm" />)}
                    </div>
                  </div>
                  {/* Contactless icon */}
                  <div className="mb-3 flex gap-0.5 items-end h-4">
                    {[2,3,4,5].map((h, i) => (
                      <div key={i} className="w-0.5 bg-amber-400/50 rounded-full" style={{height: `${h * 3}px`}} />
                    ))}
                  </div>
                  {/* Number */}
                  <div className="flex gap-3 mb-4">
                    {['1234', '5678', '9012', '2450'].map((g, i) => (
                      <span key={i} className="text-slate-200 text-sm font-mono font-bold tracking-widest">{g}</span>
                    ))}
                  </div>
                  <div className="flex items-end justify-between">
                    <div>
                      <p className="text-slate-500 text-[7px] uppercase tracking-widest">Card Holder</p>
                      <p className="text-slate-200 text-xs font-bold">JOHN A. MITCHELL</p>
                    </div>
                    <div className="text-right">
                      <p className="text-slate-500 text-[7px] uppercase tracking-widest">Expires</p>
                      <p className="text-slate-200 text-xs font-bold">12/28</p>
                    </div>
                    <div className="flex -space-x-2">
                      <div className="w-7 h-7 rounded-full bg-amber-500/80 border border-amber-400/30" />
                      <div className="w-7 h-7 rounded-full bg-amber-700/60 border border-amber-600/20" />
                    </div>
                  </div>
                </div>
              </div>

              {/* Loan approved badge removed */}
            </div>
          </div>
        </div>
      </section>

      {/* ── Stats band ── */}
      <section className="border-y border-white/10 bg-white/2 backdrop-blur-sm py-12 px-4 mb-24">
        <div className="max-w-5xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {stats.map(s => (
            <div key={s.label}>
              <div className="text-4xl font-black text-amber-400 mb-1">{s.value}</div>
              <div className="text-slate-400 text-sm font-medium">{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Benefits ── */}
      <section className="max-w-7xl mx-auto px-4 mb-24">
        <div className="text-center mb-16">
          <span className="inline-block px-4 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs font-bold uppercase tracking-widest mb-4">Why Choose Us</span>
          <h2 className="text-4xl font-black text-white mb-4">Built for Modern Lending</h2>
          <p className="text-slate-400 text-lg max-w-2xl mx-auto font-light">Everything a financial institution needs — speed, compliance, transparency, and scale.</p>
        </div>

        {/* Numbered features row + circular badge */}
        <div className="backdrop-blur-xl bg-gradient-to-r from-slate-900/80 via-slate-900/60 to-amber-950/20 border border-white/10 rounded-3xl px-10 py-10 flex flex-col lg:flex-row items-center gap-10">

          {/* Numbered items */}
          <div className="flex-1 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
            {[
              { num: '01', title: 'AI Risk Analysis', desc: 'Instantly evaluate applicants using XGBoost and SHAP-powered explainability.' },
              { num: '02', title: 'Easy To Use System', desc: 'Applicants complete KYC and loan forms in minutes from any device.' },
              { num: '03', title: 'Fraud Detection', desc: 'Payslip income verification blocks misrepresentation before processing.' },
              { num: '04', title: 'Instant Decisions', desc: 'AI delivers Approve, Review, or Reject in under 500ms — no waiting.' },
              { num: '05', title: 'Admin Oversight', desc: 'Manual review workflow lets officers verify and override AI decisions.' },
              { num: '06', title: 'Full Transparency', desc: 'Every decision comes with a plain-English explanation and audit trail.' },
            ].map(({ num, title, desc }) => (
              <div key={num} className="group">
                <p className="text-amber-400 font-black text-lg mb-1">{num}</p>
                <h4 className="text-white font-bold text-sm mb-1 group-hover:text-amber-400 transition-colors">{title}</h4>
                <p className="text-slate-500 text-xs leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>

          {/* Circular badge */}
          <div className="shrink-0 relative w-36 h-36 flex items-center justify-center">
            {/* Rotating text ring */}
            <svg viewBox="0 0 140 140" className="absolute inset-0 w-full h-full animate-spin" style={{ animationDuration: '12s' }}>
              <defs>
                <path id="circle" d="M 70,70 m -50,0 a 50,50 0 1,1 100,0 a 50,50 0 1,1 -100,0" />
              </defs>
              <text className="fill-amber-400" fontSize="11" fontWeight="700" letterSpacing="3">
                <textPath href="#circle">YOUR ONE STOP LENDING SOLUTION •</textPath>
              </text>
            </svg>
            {/* Center icon */}
            <div className="w-16 h-16 rounded-full bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center shadow-xl shadow-amber-500/30 border border-amber-300/30">
              <CheckCircle className="w-7 h-7 text-slate-950" />
            </div>
          </div>
        </div>
      </section>

      {/* ── Before You Apply ── */}
      <section className="max-w-7xl mx-auto px-4 mb-24">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">
          <div className="rounded-3xl overflow-hidden border border-white/10 shadow-xl relative">
            <img src="https://images.unsplash.com/photo-1450101499163-c8848c66ca85?w=700&q=80" alt="Documents" className="w-full h-80 object-cover" />
            <div className="absolute inset-0 bg-gradient-to-t from-slate-950/80 to-transparent" />
            <div className="absolute bottom-6 left-6 right-6">
              <p className="text-white font-black text-xl mb-1">Be Prepared.</p>
              <p className="text-slate-300 text-sm">Having the right documents speeds up verification by 3x.</p>
            </div>
          </div>
          <div>
            <span className="inline-block px-4 py-1.5 rounded-full bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-bold uppercase tracking-widest mb-4">Important</span>
            <h2 className="text-3xl font-black text-white mb-3">Before You Apply</h2>
            <p className="text-slate-400 mb-8">To ensure a smooth verification and get the most accurate decision, keep these in mind.</p>
            <div className="space-y-4">
              {[
                { icon: '📄', title: 'Prepare Your Documents', desc: 'Keep your college ID, payslip PDF, and a clear selfie ready before starting.', color: 'border-amber-500/20 bg-amber-500/5' },
                { icon: '🎯', title: 'Enter Accurate Details', desc: 'Name, DOB, and income must match exactly what appears on your official documents.', color: 'border-blue-500/20 bg-blue-500/5' },
                { icon: '💡', title: 'Good Lighting for Selfie', desc: 'Take your selfie in a well-lit room, facing the camera directly. Blurry images will fail KYC.', color: 'border-emerald-500/20 bg-emerald-500/5' },
                { icon: '⚠️', title: 'No Misrepresentation', desc: 'False income documents or mismatched IDs trigger a fraud alert and block your application.', color: 'border-red-500/20 bg-red-500/5' },
              ].map(({ icon, title, desc, color }) => (
                <div key={title} className={`flex items-start gap-4 border rounded-2xl px-5 py-4 ${color}`}>
                  <span className="text-2xl mt-0.5">{icon}</span>
                  <div>
                    <h4 className="text-white font-bold text-sm mb-1">{title}</h4>
                    <p className="text-slate-400 text-xs leading-relaxed">{desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Final CTA ── */}
      <section className="max-w-5xl mx-auto px-4">
        <div className="relative rounded-3xl overflow-hidden border border-white/10 shadow-2xl">
          <img src="https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=1200&q=80" alt="Modern Finance" className="w-full h-72 object-cover" />
          <div className="absolute inset-0 bg-gradient-to-r from-slate-950/95 via-slate-950/80 to-slate-950/60" />
          <div className="absolute inset-0 flex flex-col items-start justify-center px-10 md:px-16">
            <h2 className="text-3xl md:text-4xl font-black text-white mb-3">Ready to Get Started?</h2>
            <p className="text-slate-300 mb-8 max-w-md">Create your account in seconds. KYC verification and AI-powered loan analysis await.</p>
            <div className="flex flex-col sm:flex-row gap-4">
              <Link to="/signup" className="inline-flex items-center gap-2 bg-gradient-to-r from-amber-400 to-amber-600 text-slate-950 px-8 py-4 rounded-xl font-bold text-lg hover:scale-105 transition-all shadow-lg shadow-amber-500/25">
                Apply Now <ArrowRight className="w-5 h-5" />
              </Link>
              <Link to="/how-it-works" className="inline-flex items-center gap-2 text-white border border-white/20 px-8 py-4 rounded-xl font-semibold text-lg hover:bg-white/10 transition-all backdrop-blur-sm">
                How It Works
              </Link>
            </div>
          </div>
        </div>
      </section>

    </div>
  );
}
