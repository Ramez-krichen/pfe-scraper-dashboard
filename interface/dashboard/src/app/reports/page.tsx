"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { format } from "date-fns";

export default function ReportsPage() {
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  const fetchReports = async () => {
    try {
      const url = search ? `/api/reports?domain=${search}` : "/api/reports";
      const res = await fetch(url);
      const data = await res.json();
      setReports(data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, [search]);

  return (
    <div className="space-y-8 py-8 animate-in fade-in slide-in-from-top-4 transition-all">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <h2 className="text-3xl font-bold tracking-tight">Intelligence Reports</h2>
          <p className="text-slate-400">View and manage all historical competitive analysis scans.</p>
        </div>
        <div className="w-full md:w-64">
          <input
            type="text"
            placeholder="Search domain..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-slate-900/50 border border-slate-800 rounded-md px-4 py-2 placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all text-sm"
          />
        </div>
      </div>

      <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden backdrop-blur shadow-xl">
        <table className="w-full text-left">
          <thead className="bg-slate-900 border-b border-slate-800">
            <tr>
              <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-slate-400">Target Domain</th>
              <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-slate-400">Date</th>
              <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-slate-400">Competitors</th>
              <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-slate-400 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {loading ? (
              [...Array(5)].map((_, i) => (
                <tr key={i}>
                  <td className="px-6 py-4"><div className="h-4 bg-slate-800 rounded w-48 animate-pulse"></div></td>
                  <td className="px-6 py-4"><div className="h-4 bg-slate-800 rounded w-24 animate-pulse"></div></td>
                  <td className="px-6 py-4"><div className="h-4 bg-slate-800 rounded w-12 animate-pulse"></div></td>
                  <td className="px-6 py-4"><div className="h-4 bg-slate-800 rounded w-20 animate-pulse ml-auto"></div></td>
                </tr>
              ))
            ) : reports.length > 0 ? (
              reports.map((report) => (
                <tr key={report.id} className="hover:bg-slate-800/30 transition-colors">
                  <td className="px-6 py-4">
                    <span className="font-medium text-blue-400">{report.target_domain}</span>
                    <p className="text-xs text-slate-500 truncate max-w-xs">{report.target_url}</p>
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-400">
                    {format(new Date(report.created_at), "MMM d, yyyy HH:mm")}
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-400">{report.competitor_count}</td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex justify-end gap-3">
                      {report.pdf_url && (
                        <a href={report.pdf_url} target="_blank" className="text-xs px-2 py-1 bg-slate-800 border border-slate-700 hover:bg-slate-700 transition-colors uppercase font-bold tracking-tight rounded">PDF</a>
                      )}
                      <Link href={`/reports/${report.id}`} className="text-xs px-2 py-1 bg-blue-600 hover:bg-blue-500 transition-colors uppercase font-bold tracking-tight rounded text-white shadow-lg">View</Link>
                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={4} className="px-6 py-12 text-center text-slate-500 italic">No reports found.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
