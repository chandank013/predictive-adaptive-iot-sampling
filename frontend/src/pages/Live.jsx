import React, { useEffect, useMemo, useState } from "react";
import {
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ReferenceArea,
  ResponsiveContainer,
} from "recharts";
import { Activity, Settings, Clock, Zap, FileText, Trash2, BarChart3, Database, Play, Square, Cpu } from "lucide-react";
import {
  liveVibrationSeries as fallbackVibrationSeries,
  eventWindow,
  threshold as defaultThreshold,
  energySparkline as fallbackEnergySparkline,
  liveStats as fallbackLiveStats,
  eventLog as fallbackEventLog,
} from "../data/mockData";

const logDotColor = {
  event: "bg-red-500",
  ok: "bg-green-500",
  info: "bg-blue-500",
  warn: "bg-orange-400",
};

const POLICY_CONFIG = {
  Fixed: { samplingInterval: "1000 ms", samplingMode: "Fixed Rate", color: "bg-blue-100 text-blue-700" },
  Threshold: { samplingInterval: "250 ms", samplingMode: "Threshold", color: "bg-orange-100 text-orange-700" },
  Predictive: { samplingInterval: "100 ms", samplingMode: "High Rate", color: "bg-violet-100 text-violet-700" },
};
const POLICY_ORDER = ["Fixed", "Threshold", "Predictive"];

const G_TO_MS2 = 9.80665;
const API_BASE = "http://localhost:8000";

function StatCard({ icon, label, value, badge, badgeColor, onClick }) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag
      onClick={onClick}
      className={`card p-5 flex items-center justify-between gap-4 w-full text-left ${
        onClick ? "hover:border-navy-700 transition-colors cursor-pointer" : ""
      }`}
    >
      <div className="flex items-center gap-4">
        <div className="h-11 w-11 rounded-lg bg-slate-100 flex items-center justify-center text-navy-800">
          {icon}
        </div>
        <div>
          <p className="text-sm text-slate-500">{label}</p>
          <p className="text-xl font-bold text-slate-900">{value}</p>
        </div>
      </div>
      {badge && (
        <span className={`text-xs font-semibold px-3 py-1 rounded-full ${badgeColor}`}>{badge}</span>
      )}
    </Tag>
  );
}

function MiniStat({ icon, label, value, sub }) {
  return (
    <div className="card p-5 flex items-center gap-4">
      <div className="h-11 w-11 rounded-lg bg-slate-100 flex items-center justify-center text-navy-800">
        {icon}
      </div>
      <div>
        <p className="text-sm text-slate-500">{label}</p>
        <p className="text-xl font-bold text-slate-900">{value}</p>
        {sub && <p className="text-xs text-slate-400">{sub}</p>}
      </div>
    </div>
  );
}

export default function Live() {
  const [activePolicy, setActivePolicy] = useState("Predictive");
  const [timeWindow, setTimeWindow] = useState(60);
  const [yAxisUnit, setYAxisUnit] = useState("g");
  const [log, setLog] = useState(fallbackEventLog);
  const [rawSeries, setRawSeries] = useState(fallbackVibrationSeries);
  const [sparkline, setSparkline] = useState(fallbackEnergySparkline);
  const [stats, setStats] = useState(fallbackLiveStats);
  const [threshold, setThreshold] = useState(defaultThreshold);
  const [isLiveFromBackend, setIsLiveFromBackend] = useState(false);
  const [benchmarkLoading, setBenchmarkLoading] = useState(false);

  // Poll live data from API
  useEffect(() => {
    let isMounted = true;

    const fetchLive = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/live/latest`);
        if (res.ok) {
          const data = await res.json();
          if (isMounted) {
            setIsLiveFromBackend(true);
            if (data.chartData && data.chartData.length > 0) {
              setRawSeries(data.chartData);
            }
            if (data.energySparkline && data.energySparkline.length > 0) {
              setSparkline(data.energySparkline);
            }
            if (data.liveStats) {
              setStats(data.liveStats);
              if (data.liveStats.activePolicy) {
                setActivePolicy(data.liveStats.activePolicy);
              }
            }
            if (data.eventLog && data.eventLog.length > 0) {
              setLog(data.eventLog);
            }
            if (data.threshold) {
              setThreshold(data.threshold);
            }
          }
        }
      } catch (err) {
        if (isMounted) setIsLiveFromBackend(false);
      }
    };

    fetchLive();
    const interval = setInterval(fetchLive, 1000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const policy = POLICY_CONFIG[activePolicy] || POLICY_CONFIG["Predictive"];

  async function cyclePolicy() {
    const next = POLICY_ORDER[(POLICY_ORDER.indexOf(activePolicy) + 1) % POLICY_ORDER.length];
    setActivePolicy(next);

    try {
      await fetch(`${API_BASE}/api/policy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ policy: next.toLowerCase() }),
      });
    } catch (e) {
      console.warn("Could not push policy switch to backend:", e);
    }
  }

  async function runBenchmark() {
    setBenchmarkLoading(true);
    try {
      await fetch(`${API_BASE}/api/simulation/benchmark`, { method: "POST" });
      setTimeout(() => setBenchmarkLoading(false), 3000);
    } catch (e) {
      setBenchmarkLoading(false);
    }
  }

  const chartData = useMemo(() => {
    const maxT = rawSeries.length > 0 ? rawSeries[rawSeries.length - 1].t : 60;
    const minT = Math.max(0, maxT - timeWindow);
    const windowed = rawSeries.filter((d) => d.t >= minT);

    if (yAxisUnit === "ms2") {
      return windowed.map((d) => ({ t: d.t, value: Number((d.value * G_TO_MS2).toFixed(2)) }));
    }
    return windowed;
  }, [rawSeries, timeWindow, yAxisUnit]);

  const currentVibRaw = parseFloat(stats.currentVibration) || 0.28;
  const currentVibrationDisplay =
    yAxisUnit === "g"
      ? `${currentVibRaw.toFixed(2)} g`
      : `${(currentVibRaw * G_TO_MS2).toFixed(2)} m/s²`;

  const yDomain = yAxisUnit === "g" ? [0, 2] : [0, 20];
  const yLabel = yAxisUnit === "g" ? "Acceleration (g)" : "Acceleration (m/s²)";
  const thresholdValue = yAxisUnit === "g" ? threshold : Number((threshold * G_TO_MS2).toFixed(2));
  const thresholdLabel = yAxisUnit === "g" ? `Threshold (${threshold} g)` : `Threshold (${thresholdValue} m/s²)`;

  return (
    <div className="max-w-[1680px] mx-auto px-6 py-6 space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
        {/* Left column: chart card + bottom stat grid */}
        <div className="flex flex-col gap-3">
          {/* Main chart card */}
          <div className="card p-6">
            <div className="flex items-start justify-between flex-wrap gap-3 mb-4">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-lg bg-sky-50 flex items-center justify-center text-sky-600">
                  <Activity size={20} />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-bold text-slate-900">Live Vibration Sensor Telemetry</h2>
                    <span className="text-[11px] font-semibold bg-amber-100 text-amber-800 px-2 py-0.5 rounded-full">
                      Simulated ADXL345
                    </span>
                  </div>
                  <p className="text-xs text-slate-500">
                    Real-time acceleration deviation from 1g baseline ({isLiveFromBackend ? "Streaming from simulation engine" : "Standalone preview mode"})
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={runBenchmark}
                  disabled={benchmarkLoading}
                  className="text-xs font-semibold bg-navy-900 text-white hover:bg-navy-800 px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-colors disabled:opacity-50"
                  title="Run deterministic 3-policy comparison trial"
                >
                  <Cpu size={14} />
                  {benchmarkLoading ? "Benchmarking..." : "Run Benchmark"}
                </button>
                <select
                  value={yAxisUnit}
                  onChange={(e) => setYAxisUnit(e.target.value)}
                  className="text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 text-slate-600 bg-white"
                >
                  <option value="g">Y: Acceleration (g)</option>
                  <option value="ms2">Y: Acceleration (m/s²)</option>
                </select>
                <select
                  value={timeWindow}
                  onChange={(e) => setTimeWindow(Number(e.target.value))}
                  className="text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 text-slate-600 bg-white"
                >
                  <option value={30}>Window: 30 s</option>
                  <option value={60}>Window: 60 s</option>
                </select>
              </div>
            </div>

            <ResponsiveContainer width="100%" height={340}>
              <AreaChart data={chartData} margin={{ top: 20, right: 10, left: 10, bottom: 20 }}>
                <CartesianGrid stroke="#eef0f2" vertical={false} />
                <XAxis
                  dataKey="t"
                  type="number"
                  tick={{ fontSize: 12, fill: "#8a97a0" }}
                  label={{ value: "Time (seconds)", position: "insideBottom", offset: -5, fontSize: 12, fill: "#8a97a0" }}
                />
                <YAxis
                  domain={yDomain}
                  tick={{ fontSize: 12, fill: "#8a97a0" }}
                  label={{ value: yLabel, angle: -90, position: "insideLeft", fontSize: 12, fill: "#8a97a0" }}
                />
                <Tooltip
                  formatter={(val) => [`${val} ${yAxisUnit}`, "Acceleration"]}
                  labelFormatter={(lbl) => `t = ${lbl}s`}
                />
                <ReferenceLine
                  y={thresholdValue}
                  stroke="#d94b4b"
                  strokeDasharray="6 4"
                  label={{ value: thresholdLabel, position: "insideTopLeft", fontSize: 11, fill: "#d94b4b" }}
                />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke="#0d3b4f"
                  strokeWidth={2}
                  fill="#0d3b4f"
                  fillOpacity={0.08}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Bottom mini stats */}
          <div className="grid grid-cols-2 gap-x-5 gap-y-1">
            <MiniStat
              icon={<Activity size={20} />}
              label="Current Vibration"
              value={currentVibrationDisplay}
              sub={`↓ ${stats.vibrationChange}`}
            />
            <MiniStat
              icon={<BarChart3 size={20} />}
              label="Sampling Rate"
              value={stats.samplingRate}
              sub={stats.samplingRateSub}
            />
            <MiniStat
              icon={<Database size={20} />}
              label="Packets Sent"
              value={stats.packetsSent}
              sub={stats.packetsSentSub}
            />
            <MiniStat
              icon={<Clock size={20} />}
              label="Uptime"
              value={stats.uptime}
              sub={stats.uptimeSub}
            />
          </div>
        </div>

        {/* Right sidebar stats */}
        <div className="flex flex-col gap-5">
          <StatCard
            icon={<Settings size={20} />}
            label="Active Policy (click to cycle)"
            value={activePolicy}
            badge={activePolicy}
            badgeColor={policy.color}
            onClick={cyclePolicy}
          />
          <StatCard
            icon={<Clock size={20} />}
            label="Current Sampling Interval"
            value={stats.samplingInterval}
            badge={stats.samplingMode}
            badgeColor={policy.color}
          />
          <div className="card p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="h-11 w-11 rounded-lg bg-slate-100 flex items-center justify-center text-navy-800">
                  <Zap size={20} />
                </div>
                <div>
                  <p className="text-sm text-slate-500">Current Draw (INA219)</p>
                  <p className="text-xl font-bold text-slate-900">{stats.energyDraw}</p>
                </div>
              </div>
              <div className="w-24 h-10">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={sparkline}>
                    <Line type="monotone" dataKey="value" stroke="#1a9b6c" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="card p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 font-bold text-slate-900">
                <FileText size={18} />
                Event Log
              </div>
              <button
                onClick={() => setLog([])}
                disabled={log.length === 0}
                className="text-xs text-blue-600 font-medium flex items-center gap-1 hover:underline disabled:text-slate-300 disabled:no-underline disabled:cursor-not-allowed"
              >
                <Trash2 size={14} /> Clear Log
              </button>
            </div>
            {log.length === 0 ? (
              <p className="text-sm text-slate-400 py-4 text-center">No events logged.</p>
            ) : (
              <ul className="space-y-3 max-h-[260px] overflow-y-auto pr-1">
                {log.map((e) => (
                  <li key={e.id} className="flex items-start justify-between text-sm">
                    <div className="flex items-start gap-2">
                      <span className={`mt-1.5 h-2 w-2 rounded-full shrink-0 ${logDotColor[e.type] || "bg-slate-400"}`} />
                      <span className="text-slate-700">{e.text}</span>
                    </div>
                    <span className="text-slate-400 shrink-0 ml-2 text-xs">{e.time}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
