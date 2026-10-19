import React, { useMemo, useState } from "react";
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
import { Activity, Settings, Clock, Zap, FileText, Trash2, BarChart3, Database } from "lucide-react";
import {
  liveVibrationSeries,
  eventWindow,
  threshold,
  energySparkline,
  liveStats,
  eventLog,
} from "../data/mockData";

const logDotColor = {
  event: "bg-red-500",
  ok: "bg-green-500",
  info: "bg-blue-500",
  warn: "bg-orange-400",
};

// Cycling through this (via the Active Policy card) updates the sampling
// interval card and its badge to match — real behavior, not decoration.
const POLICY_CONFIG = {
  Fixed: { samplingInterval: "1000 ms", samplingMode: "Fixed Rate", color: "bg-blue-100 text-blue-700" },
  Threshold: { samplingInterval: "250 ms", samplingMode: "Threshold", color: "bg-orange-100 text-orange-700" },
  Predictive: { samplingInterval: "100 ms", samplingMode: "High Rate", color: "bg-violet-100 text-violet-700" },
};
const POLICY_ORDER = ["Fixed", "Threshold", "Predictive"];

// g -> m/s^2 conversion for the Y-axis unit toggle.
const G_TO_MS2 = 9.80665;

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
  const [timeWindow, setTimeWindow] = useState(60); // seconds shown on the chart
  const [yAxisUnit, setYAxisUnit] = useState("g"); // "g" or "ms2"
  const [log, setLog] = useState(eventLog);

  const policy = POLICY_CONFIG[activePolicy];

  function cyclePolicy() {
    const next = POLICY_ORDER[(POLICY_ORDER.indexOf(activePolicy) + 1) % POLICY_ORDER.length];
    setActivePolicy(next);
  }

  // Real data transforms driven by the two chart dropdowns.
  const chartData = useMemo(() => {
    const windowed = liveVibrationSeries.filter((d) => d.t >= 60 - timeWindow);
    if (yAxisUnit === "ms2") {
      return windowed.map((d) => ({ t: d.t, value: Number((d.value * G_TO_MS2).toFixed(2)) }));
    }
    return windowed;
  }, [timeWindow, yAxisUnit]);

  // Current Vibration card follows the same unit toggle as the chart.
  const currentVibrationG = 0.28;
  const currentVibrationDisplay =
    yAxisUnit === "g"
      ? `${currentVibrationG.toFixed(2)} g`
      : `${(currentVibrationG * G_TO_MS2).toFixed(2)} m/s\u00b2`;

  const yDomain = yAxisUnit === "g" ? [0, 2] : [0, 20];
  const yLabel = yAxisUnit === "g" ? "Acceleration (g)" : "Acceleration (m/s\u00b2)";
  const thresholdValue = yAxisUnit === "g" ? threshold : Number((threshold * G_TO_MS2).toFixed(2));
  const thresholdLabel = yAxisUnit === "g" ? "Threshold (1.0 g)" : `Threshold (${thresholdValue} m/s\u00b2)`;

  return (
    <div className="max-w-[1680px] mx-auto px-6 py-6 space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
        {/* Left column: chart card + bottom stat grid, same width */}
        <div className="flex flex-col gap-3">
          {/* Main chart card */}
          <div className="card p-6">
            <div className="flex items-start justify-between flex-wrap gap-3 mb-4">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-lg bg-sky-50 flex items-center justify-center text-sky-600">
                  <Activity size={20} />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-slate-900">Live Vibration Sensor Reading</h2>
                  <p className="text-sm text-slate-500">Real-time accelerometer data (ADXL345)</p>
                </div>
              </div>
              <div className="flex gap-2">
                <select
                  value={yAxisUnit}
                  onChange={(e) => setYAxisUnit(e.target.value)}
                  className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 text-slate-600"
                >
                  <option value="g">Y-axis: Acceleration (g)</option>
                  <option value="ms2">Y-axis: Acceleration (m/s²)</option>
                </select>
                <select
                  value={timeWindow}
                  onChange={(e) => setTimeWindow(Number(e.target.value))}
                  className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 text-slate-600"
                >
                  <option value={30}>Time Window: 30 s</option>
                  <option value={60}>Time Window: 60 s</option>
                </select>
              </div>
            </div>

            <ResponsiveContainer width="100%" height={340}>
              <AreaChart data={chartData} margin={{ top: 20, right: 10, left: 10, bottom: 20 }}>
                <CartesianGrid stroke="#eef0f2" vertical={false} />
                <XAxis
                  dataKey="t"
                  domain={[60 - timeWindow, 60]}
                  type="number"
                  tick={{ fontSize: 12, fill: "#8a97a0" }}
                  label={{ value: "Time (seconds)", position: "insideBottom", offset: -5, fontSize: 12, fill: "#8a97a0" }}
                />
                <YAxis
                  domain={yDomain}
                  tick={{ fontSize: 12, fill: "#8a97a0" }}
                  label={{ value: yLabel, angle: -90, position: "insideLeft", fontSize: 12, fill: "#8a97a0" }}
                />
                <Tooltip />
                <ReferenceArea
                  x1={Math.max(eventWindow.start, 60 - timeWindow)}
                  x2={eventWindow.end}
                  fill="#d94b4b"
                  fillOpacity={0.08}
                  label={{ value: "Event Detected", position: "top", fill: "#d94b4b", fontSize: 12, fontWeight: 600 }}
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

          {/* Bottom mini stats — 2x2 grid, same width as the chart card above */}
          <div className="grid grid-cols-2 gap-x-5 gap-y-1">
            <MiniStat
              icon={<Activity size={20} />}
              label="Current Vibration"
              value={currentVibrationDisplay}
              sub={`\u2193 ${liveStats.vibrationChange}`}
            />
            <MiniStat
              icon={<BarChart3 size={20} />}
              label="Sampling Rate"
              value={liveStats.samplingRate}
              sub={liveStats.samplingRateSub}
            />
            <MiniStat
              icon={<Database size={20} />}
              label="Packets Sent"
              value={liveStats.packetsSent}
              sub={liveStats.packetsSentSub}
            />
            <MiniStat
              icon={<Clock size={20} />}
              label="Uptime"
              value={liveStats.uptime}
              sub={liveStats.uptimeSub}
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
            value={policy.samplingInterval}
            badge={policy.samplingMode}
            badgeColor={policy.color}
          />
          <div className="card p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="h-11 w-11 rounded-lg bg-slate-100 flex items-center justify-center text-navy-800">
                  <Zap size={20} />
                </div>
                <div>
                  <p className="text-sm text-slate-500">Energy Draw</p>
                  <p className="text-xl font-bold text-slate-900">{liveStats.energyDraw}</p>
                </div>
              </div>
              <div className="w-24 h-10">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={energySparkline}>
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
                      <span className={`mt-1.5 h-2 w-2 rounded-full shrink-0 ${logDotColor[e.type]}`} />
                      <span className="text-slate-700">{e.text}</span>
                    </div>
                    <span className="text-slate-400 shrink-0 ml-2">{e.time}</span>
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
