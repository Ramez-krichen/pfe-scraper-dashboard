"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [polling, setPolling] = useState(false);
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setStatus(null);

    try {
      const res = await fetch("/api/trigger", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, triggeredBy: "dashboard" }),
      });

      const data = await res.json();
      if (data.runId) {
        setPolling(true);
        setStatus({ status: "running" });
      }
    } catch (error) {
      console.error(error);
      alert("Failed to start analysis");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!polling || !url) return;

    const domain = new URL(url).hostname;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/status?domain=${domain}`);
        const data = await res.json();
        setStatus(data);

        if (data.status === "completed" || data.status === "failed") {
          setPolling(false);
          clearInterval(interval);
          if (data.report_id) {
            router.push(`/reports/${data.report_id}`);
          }
        }
      } catch (err) {
        console.error(err);
      }
    }, 15000);

    return () => clearInterval(interval);
  }, [polling, url, router]);

  return (
    <div className="max-w-xl mx-auto space-y-8 py-12">
      <div className="text-center space-y-2">
        <h2 className="text-3xl font-bold tracking-tight">New Analysis</h2>
        <p className="text-slate-400">Enter a target ecommerce URL to start competitive analysis.</p>
      </div>

      <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-8 backdrop-blur shadow-xl">
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <label htmlFor="url" className="text-sm font-medium text-slate-300">Target Website URL</label>
            <input
              id="url"
              type="url"
              placeholder="https://example.com"
              required
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-md px-4 py-3 placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all"
            />
          </div>
          <button
            type="submit"
            disabled={isLoading || polling}
            className={`w-full py-3 px-4 rounded-md font-semibold text-white shadow-lg transition-all ${
              isLoading || polling ? 'bg-slate-700 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-500 hover:shadow-blue-500/25 active:scale-[0.98]'
            }`}
          >
            {isLoading ? "Starting..." : polling ? "Analysis in progress..." : "Run Analysis"}
          </button>
        </form>

        {status && (
          <div className="mt-8 p-6 rounded-lg bg-slate-950/50 border border-slate-800 space-y-3 animate-in fade-in slide-in-from-bottom-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-slate-400">Current Status</span>
              <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wider ${
                status.status === 'running' ? 'bg-blue-500/10 text-blue-400 animate-pulse' :
                status.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400' :
                'bg-red-500/10 text-red-400'
              }`}>
                {status.status}
              </span>
            </div>
            {status.status === 'running' && (
              <p className="text-sm text-slate-500 italic">This usually takes 10–20 minutes. You can leave this page and check "Runs" later.</p>
            )}
            {status.error_message && (
              <p className="text-xs text-red-400 font-mono p-2 bg-red-400/5 rounded border border-red-400/10">{status.error_message}</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
