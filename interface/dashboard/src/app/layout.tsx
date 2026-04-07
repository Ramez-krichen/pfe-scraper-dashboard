import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Competitive Intelligence Dashboard",
  description: "Monitor and analyze competitor ecommerce sites",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-slate-950 text-slate-50 antialiased min-h-screen`}>
        <div className="flex h-screen overflow-hidden">
          {/* Sidebar */}
          <aside className="w-64 border-r border-slate-800 bg-slate-900/50 flex-none h-full hidden md:flex flex-col">
            <div className="p-6">
              <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
                Intel System
              </h1>
            </div>
            <nav className="flex-1 px-4 space-y-1">
              <a href="/" className="flex items-center px-3 py-2 text-sm font-medium rounded-md hover:bg-slate-800 text-slate-300 hover:text-white transition-colors">
                New Analysis
              </a>
              <a href="/reports" className="flex items-center px-3 py-2 text-sm font-medium rounded-md hover:bg-slate-800 text-slate-300 hover:text-white transition-colors">
                Reports
              </a>
              <a href="/runs" className="flex items-center px-3 py-2 text-sm font-medium rounded-md hover:bg-slate-800 text-slate-300 hover:text-white transition-colors">
                Run Log
              </a>
            </nav>
          </aside>

          {/* Main Content */}
          <main className="flex-1 overflow-y-auto relative">
            <div className="max-w-7xl mx-auto p-4 md:p-8">
              {children}
            </div>
          </main>
        </div>
      </body>
    </html>
  );
}
