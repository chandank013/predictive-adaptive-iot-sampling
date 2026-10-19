import React from "react";

const TABS = ["Live Monitoring", "Trial Results", "Trial History"];

export default function Navbar({ activeTab, onChangeTab }) {
  return (
    <header className="bg-navy-900 text-white">
      <div className="max-w-[1680px] mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <img src="/logo.png" alt="Adaptive IoT Sensing logo" className="h-12 w-auto" />
          <span className="text-xl font-bold tracking-tight"></span>
        </div>

        <nav className="hidden md:flex items-stretch gap-10 self-stretch">
          {TABS.map((tab) => {
            const isActive = tab === activeTab;
            return (
              <button
                key={tab}
                onClick={() => onChangeTab(tab)}
                className={`flex flex-col items-center justify-center gap-2 text-[15px] transition-colors ${
                  isActive ? "text-white font-semibold" : "text-slate-300 hover:text-white font-medium"
                }`}
              >
                {tab}
                <span
                  className={`h-[3px] w-full rounded-full ${isActive ? "bg-white" : "bg-transparent"}`}
                />
              </button>
            );
          })}
        </nav>

        <div className="flex items-center gap-2 bg-accent-green/20 border border-accent-green/40 text-green-300 text-sm font-medium px-3 py-1.5 rounded-full">
          <span className="h-2 w-2 rounded-full bg-accent-green inline-block" />
          Connected
        </div>
      </div>
    </header>
  );
}
