import React, { useEffect, useState } from "react";

const TABS = ["Live Monitoring", "Trial Results", "Trial History"];

export default function Navbar({ activeTab, onChangeTab }) {
  const [backendConnected, setBackendConnected] = useState(false);
  const [systemMode, setSystemMode] = useState("SIMULATION");

  useEffect(() => {
    let isMounted = true;
    const checkHealth = async () => {
      try {
        const res = await fetch("http://localhost:8000/health", { method: "GET" });
        if (res.ok) {
          const data = await res.json();
          if (isMounted) {
            setBackendConnected(true);
            setSystemMode(data.system_mode || "SIMULATION");
          }
        } else {
          if (isMounted) setBackendConnected(false);
        }
      } catch (err) {
        if (isMounted) setBackendConnected(false);
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 3000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <header className="bg-navy-900 text-white">
      <div className="max-w-[1680px] mx-auto px-6 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <img src="/logo.png" alt="Adaptive IoT Sensing logo" className="h-11 w-auto" />
          <span className="text-lg font-bold tracking-tight text-white hidden sm:inline">
            Predictive Adaptive IoT Sensing
          </span>
        </div>

        <nav className="hidden md:flex items-stretch gap-8 self-stretch">
          {TABS.map((tab) => {
            const isActive = tab === activeTab;
            return (
              <button
                key={tab}
                onClick={() => onChangeTab(tab)}
                className={`flex flex-col items-center justify-center gap-1.5 text-[15px] transition-colors ${
                  isActive ? "text-white font-semibold" : "text-slate-300 hover:text-white font-medium"
                }`}
              >
                {tab}
                <span
                  className={`h-[3px] w-full rounded-full transition-all ${
                    isActive ? "bg-accent-green" : "bg-transparent"
                  }`}
                />
              </button>
            );
          })}
        </nav>

        <div className="flex items-center gap-3">
          {backendConnected ? (
            <div className="flex items-center gap-2 bg-emerald-950/60 border border-emerald-500/40 text-emerald-300 text-xs font-semibold px-3 py-1.5 rounded-full">
              <span className="h-2 w-2 rounded-full bg-emerald-400 inline-block animate-ping" />
              API Connected
            </div>
          ) : (
            <div className="flex items-center gap-2 bg-amber-950/60 border border-amber-500/40 text-amber-300 text-xs font-semibold px-3 py-1.5 rounded-full">
              <span className="h-2 w-2 rounded-full bg-amber-400 inline-block" />
              Standalone Mode
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
