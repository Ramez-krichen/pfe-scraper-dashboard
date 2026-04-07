"use client";

import { useState, useEffect } from "react";
import { format } from "date-fns";
import Link from "next/link";

export default function RunLogPage() {
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchRuns = async () => {
    try {
      const res = await fetch("/api/runs");
      const data = await res.json();
      setRuns(data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRuns();
    const interval = setInterval(fetchRuns, 10000); // Auto-refresh every 10 seconds
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-8 py-8 animate-in fade-in slide-in-from-right-4 transition-all pb-24">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <h2 className="text-3xl font-bold tracking-tight">System Run Log</h2>
          <p className="text-slate-400">Live monitoring of all background competitive scans.</p>
        </div>
        <div className="flex items-center gap-2 text-xs font-bold text-slate-500 uppercase tracking-widest bg-slate-900 border border-slate-800 px-4 py-2 rounded-full">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          Live Monitoring Active
        </div>
      </div>

      <div className="bg-slate-900/50 border border-slate-800 rounded-2xl overflow-hidden backdrop-blur shadow-2xl">
        <table className="w-full text-left">
          <thead className="bg-slate-900 border-b border-slate-800 text-xs font-black uppercase tracking-widest text-slate-500">
            <tr>
              <th className="px-6 py-5">Target URL</th>
              <th className="px-6 py-5">Status</th>
              <th className="px-6 py-5">Triggered By</th>
              <th className="px-6 py-5 text-right">Started At</th>
              <th className="px-6 py-5 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {loading ? (
              [...Array(8)].map((_, i) => (
                <tr key={i}>
                  <td className="px-6 py-4"><div className="h-4 bg-slate-800 rounded w-64 animate-pulse"></div></td>
                  <td className="px-6 py-4"><div className="h-6 bg-slate-800 rounded w-20 animate-pulse"></div></td>
                  <td className="px-6 py-4"><div className="h-4 bg-slate-800 rounded w-24 animate-pulse"></div></td>
                  <td className="px-6 py-4"><div className="h-4 bg-slate-800 rounded w-32 animate-pulse ml-auto"></div></td>
                  <td className="px-6 py-4"><div className="h-6 bg-slate-800 rounded w-16 animate-pulse ml-auto"></div></td>
                </tr>
              ))
            ) : runs.map((run) => (
              <tr key={run.id} className={`hover:bg-slate-800/20 transition-colors ${run.status === 'running' ? 'bg-blue-500/5' : ''}`}>
                <td className="px-6 py-5 max-w-md">
                   <p className="text-sm font-bold text-slate-300 truncate">{run.target_url}</p>
                </td>
                <td className="px-6 py-5">
                  <span className={`px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest border transition-all ${
                    run.status === 'running' ? 'bg-blue-500/10 text-blue-400 border-blue-400/20 animate-pulse' :
                    run.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-400/20 shadow-sm shadow-emerald-500/10' :
                    'bg-red-500/10 text-red-100 border-red-500/20 shadow-sm shadow-red-500/10'
                  }`}>
                    {run.status}
                  </span>
                </td>
                <td className="px-6 py-5">
                  <span className="text-[10px] bg-slate-800 text-slate-400 px-2 py-1 rounded font-bold uppercase tracking-tight">{run.triggered_by}</span>
                </td>
                <td className="px-6 py-5 text-right text-xs text-slate-500 font-mono">
                  {format(new Date(run.started_at), "HH:mm:ss dd/MM")}
                </td>
                <td className="px-6 py-5 text-right">
                   {run.report_id ? (
                     <Link href={`/reports/${run.report_id}`} className="text-blue-400 hover:text-white transition-colors text-xs font-bold uppercase tracking-tighter">View Report</Link>
                   ) : run.status === 'failed' ? (
                     <div className="relative group inline-block">
                        <span className="text-red-400 text-xs font-bold uppercase cursor-help">Error</span>
                        <div className="absolute bottom-full right-0 mb-2 invisible group-hover:visible w-64 p-3 bg-slate-950 border border-red-500/20 text-[10px] leading-relaxed text-red-200 rounded-xl shadow-2xl z-50">
                           {run.error_message || "Unknown error occurred"}
                        </div>
                     </div>
                   ) : (
                     <span className="text-slate-700 text-xs font-bold uppercase tracking-widest">–</span>
                   )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
