import React from 'react';
import { Outlet } from 'react-router-dom';

export default function AdminLayout() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 relative overflow-x-hidden">
      {/* Same ambient glows as MainLayout */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <div className="absolute top-[-15%] left-[-10%] w-[60%] h-[60%] rounded-full bg-amber-500/8 blur-[160px]" />
        <div className="absolute top-[50%] right-[-15%] w-[50%] h-[50%] rounded-full bg-indigo-700/8 blur-[140px]" />
        <div className="absolute bottom-[-10%] left-[30%] w-[40%] h-[40%] rounded-full bg-amber-600/5 blur-[120px]" />
      </div>
      <div className="relative z-10">
        <Outlet />
      </div>
    </div>
  );
}
