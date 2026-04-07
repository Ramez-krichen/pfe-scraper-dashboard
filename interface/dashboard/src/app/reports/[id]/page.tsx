"use client";

import { useState, useEffect } from "react";
import { format } from "date-fns";
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell 
} from "recharts";

export default function ReportDetailPage({ params }: { params: { id: string } }) {
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchReport = async () => {
      try {
        const res = await fetch(`/api/reports/${params.id}`);
        const data = await res.json();
        setReport(data);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    };
    fetchReport();
  }, [params.id]);

  if (loading) return <div className="py-20 text-center text-slate-500 animate-pulse">Loading intelligence report...</div>;
  if (!report) return <div className="py-20 text-center text-red-500">Report not found.</div>;

  const data = report.report_data || {};
  const target = data.target_site || {};
  const competitors = data.competitors || [];
  
  // Prepare price comparison data for chart
  const priceData = [
    { name: "Target", price: target.avg_price || 0, isTarget: true },
    ...competitors.map((c: any) => ({
      name: c.domain,
      price: c.avg_price || 0,
      isTarget: false
    }))
  ].slice(0, 6);

  return (
    <div className="space-y-10 py-8 animate-in fade-in slide-in-from-bottom-4 transition-all pb-20">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 border-b border-slate-800">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <h2 className="text-4xl font-extrabold tracking-tight text-white">{report.target_domain}</h2>
            <span className="px-3 py-1 rounded bg-blue-500/10 text-blue-400 text-xs font-bold uppercase tracking-widest border border-blue-400/20 shadow-sm shadow-blue-500/30">Target System</span>
          </div>
          <p className="text-slate-400 font-medium">Analysis conducted on {format(new Date(report.created_at), "MMMM d, yyyy 'at' HH:mm")}</p>
        </div>
        <div className="flex gap-4">
          {report.pdf_url && (
            <a href={report.pdf_url} target="_blank" className="px-6 py-3 bg-slate-100 hover:bg-white text-slate-900 rounded-lg font-bold text-sm transition-all shadow-lg shadow-white/5 uppercase tracking-tight">Download PDF Report</a>
          )}
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-slate-900/40 border border-slate-800 p-6 rounded-2xl backdrop-blur-sm shadow-inner group transition-all hover:bg-slate-800/20">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-1 group-hover:text-blue-400 transition-colors">Catalog Size</p>
          <div className="text-3xl font-black text-white">{target.product_count?.toLocaleString() || "0"} <span className="text-sm font-medium text-slate-600 tracking-tight">Products</span></div>
        </div>
        <div className="bg-slate-900/40 border border-slate-800 p-6 rounded-2xl backdrop-blur-sm shadow-inner group transition-all hover:bg-emerald-800/20">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-1 group-hover:text-emerald-400 transition-colors">Performance Score</p>
          <div className="text-3xl font-black text-emerald-400">{target.performance_score || "N/A"} <span className="text-sm font-medium text-slate-600 tracking-tight">/ 100</span></div>
        </div>
        <div className="bg-slate-900/40 border border-slate-800 p-6 rounded-2xl backdrop-blur-sm shadow-inner group transition-all hover:bg-purple-800/20">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-1 group-hover:text-purple-400 transition-colors">Competitors Found</p>
          <div className="text-3xl font-black text-white">{report.competitor_count} <span className="text-sm font-medium text-slate-600 tracking-tight">Discovery</span></div>
        </div>
        <div className="bg-slate-900/40 border border-slate-800 p-6 rounded-2xl backdrop-blur-sm shadow-inner group transition-all hover:bg-amber-800/20">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-1 group-hover:text-amber-400 transition-colors">Avg. SKU Price</p>
          <div className="text-3xl font-black text-white">${target.avg_price?.toFixed(2) || "0.00"} <span className="text-sm font-medium text-slate-600 tracking-tight">Market</span></div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Price Comparison Chart */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-slate-900/80 border border-slate-800/50 rounded-3xl p-8 backdrop-blur-xl shadow-2xl">
            <h3 className="text-xl font-bold text-white mb-8 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-500"></span>
              Price Indexing Comparison
            </h3>
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={priceData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.3} />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} />
                  <YAxis hide />
                  <Tooltip 
                    cursor={{ fill: 'rgba(51, 65, 85, 0.4)' }}
                    contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '12px' }}
                  />
                  <Bar dataKey="price" radius={[8, 8, 0, 0]} barSize={40}>
                    {priceData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.isTarget ? '#3b82f6' : '#475569'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="text-xs text-center text-slate-500 mt-4 uppercase tracking-widest font-bold">Average Product Price Comparison (USD)</p>
          </div>

          <div className="space-y-6">
             <h3 className="text-2xl font-black text-white tracking-tight">Competitor Landscape</h3>
             <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
               {competitors.map((comp: any, idx: number) => (
                 <div key={idx} className="bg-slate-900/50 border border-slate-800 p-6 rounded-2xl shadow-lg relative overflow-hidden group hover:border-slate-700 transition-all">
                    <div className="flex justify-between items-start mb-4">
                      <div>
                        <h4 className="text-lg font-bold text-blue-400">{comp.domain}</h4>
                        <p className="text-xs text-slate-500 truncate">{comp.url}</p>
                      </div>
                      <span className={`text-[10px] font-black px-2 py-0.5 rounded uppercase tracking-wider ${
                        comp.avg_price < target.avg_price ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
                      }`}>
                        {comp.avg_price < target.avg_price ? 'Cheaper' : 'More Expensive'}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div className="space-y-1">
                        <p className="text-slate-500 text-[10px] font-bold uppercase tracking-widest">Performance</p>
                        <p className="font-bold text-white">{comp.performance_score || "N/A"}</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-slate-500 text-[10px] font-bold uppercase tracking-widest">SKUs</p>
                        <p className="font-bold text-white">{comp.product_count || 0}</p>
                      </div>
                    </div>
                    <div className="mt-4 pt-4 border-t border-slate-800">
                      <p className="text-slate-500 text-[10px] font-bold uppercase tracking-widest mb-2">Top Tech Stack</p>
                      <div className="flex flex-wrap gap-1">
                        {(comp.tech_stack || []).slice(0, 3).map((tech: string, tIdx: number) => (
                          <span key={tIdx} className="text-[10px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded">{tech}</span>
                        ))}
                      </div>
                    </div>
                 </div>
               ))}
             </div>
          </div>
        </div>

        {/* AI Recommendations */}
        <div className="space-y-8">
            <div className="bg-gradient-to-br from-indigo-600/90 to-blue-700/90 p-8 rounded-3xl shadow-2xl shadow-blue-900/20 relative overflow-hidden group">
               <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                  <svg className="w-32 h-32 text-white" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z"></path></svg>
               </div>
               <h3 className="text-xl font-bold text-white mb-6 relative z-10 flex items-center gap-2 italic">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                  AI Strategic Advice
               </h3>
               <div className="space-y-4 text-blue-50 relative z-10 text-sm leading-relaxed">
                  {data.ai_summary?.split('\n').map((para: string, pIdx: number) => (
                    <p key={pIdx}>{para}</p>
                  )) || "Generating strategic summary..."}
               </div>
               <div className="mt-8 pt-8 border-t border-white/10 relative z-10">
                  <p className="text-white/50 text-[10px] font-bold uppercase tracking-widest leading-none">Confidence Score</p>
                  <p className="text-2xl font-black text-white italic">High Reliability</p>
               </div>
            </div>

            <div className="bg-slate-900/50 border border-slate-800 p-8 rounded-3xl shadow-xl backdrop-blur-sm">
               <h3 className="text-xl font-bold text-white mb-6">Market Gaps Found</h3>
               <ul className="space-y-4">
                  {(data.market_gaps || []).map((gap: string, gIdx: number) => (
                    <li key={gIdx} className="flex gap-3 text-sm text-slate-300">
                      <span className="flex-none w-5 h-5 rounded-full bg-amber-500/10 text-amber-500 flex items-center justify-center text-[10px] font-black border border-amber-500/20 transition-all hover:scale-110">!</span>
                      {gap}
                    </li>
                  ))}
               </ul>
            </div>
        </div>
      </div>
    </div>
  );
}
