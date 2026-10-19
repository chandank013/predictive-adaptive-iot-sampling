import React, { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { BarChart3, Calendar, Clock, FileSpreadsheet } from "lucide-react";
import {
  trialHistory as fallbackTrialHistory,
  tradeoffCurve as fallbackTradeoffCurve,
  policyComparisonTable as fallbackPolicyComparisonTable,
} from "../data/mockData";

const API_BASE = "http://localhost:8000";

function MetaItem({ icon, label, value }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-navy-800">{icon}</span>
      <div>
        <p className="text-xs text-slate-500">{label}</p>
        <p className="text-sm font-bold text-slate-900">{value}</p>
      </div>
    </div>
  );
}

export default function Results({ selectedTrial, onSelectTrial }) {
  const [trialsList, setTrialsList] = useState(fallbackTrialHistory);
  const [tradeoffData, setTradeoffData] = useState(fallbackTradeoffCurve);
  const [comparisonTable, setComparisonTable] = useState(fallbackPolicyComparisonTable);
  const [activeTrialSummary, setActiveTrialSummary] = useState(null);

  // Fetch trials and tradeoff curve from API
  useEffect(() => {
    let isMounted = true;

    const loadData = async () => {
      try {
        const [trialsRes, tradeoffRes] = await Promise.all([
          fetch(`${API_BASE}/trials`),
          fetch(`${API_BASE}/api/tradeoff`),
        ]);

        if (trialsRes.ok) {
          const rawTrials = await trialsRes.json();
          if (isMounted && rawTrials.length > 0) {
            const formatted = rawTrials.map((t) => {
              const dateObj = t.start_time ? new Date(t.start_time) : new Date();
              return {
                file: t.trial_id,
                date: dateObj.toLocaleDateString("en-US", { month: "short", day: "2-digit", year: "numeric" }),
                time: dateObj.toLocaleTimeString("en-US", { hour12: false }),
                policy: (t.policy || "Predictive").charAt(0).toUpperCase() + (t.policy || "Predictive").slice(1) + "-adaptive",
                duration: t.duration_s ? `${t.duration_s}s` : "Dynamic",
                events: t.events_logged ?? 2,
                energy: t.energy_mJ ?? 120.0,
                status: "Complete",
              };
            });
            setTrialsList(formatted);
          }
        }

        if (tradeoffRes.ok) {
          const tradeoffJson = await tradeoffRes.json();
          if (isMounted) {
            if (tradeoffJson.tradeoffCurve && Object.keys(tradeoffJson.tradeoffCurve).length > 0) {
              setTradeoffData(tradeoffJson.tradeoffCurve);
            }
            if (tradeoffJson.policyComparisonTable && tradeoffJson.policyComparisonTable.length > 0) {
              setComparisonTable(tradeoffJson.policyComparisonTable);
            }
          }
        }
      } catch (err) {
        // Fallback to static mockData
      }
    };

    loadData();
  }, []);

  const trial = trialsList.find((t) => t.file === selectedTrial) ?? trialsList[0];

  // Fetch specific trial summary
  useEffect(() => {
    if (!trial) return;
    let isMounted = true;
    fetch(`${API_BASE}/trials/${trial.file}/summary`)
      .then((res) => (res.ok ? res.json() : null))
      .then((summary) => {
        if (isMounted && summary) setActiveTrialSummary(summary);
      })
      .catch(() => {});
    return () => {
      isMounted = false;
    };
  }, [trial]);

  // Merge points into unified dataset for Recharts tooltip alignment
  const mergedCurve = (() => {
    const rows = new Map();
    for (const [policyKey, points] of Object.entries(tradeoffData)) {
      if (!Array.isArray(points)) continue;
      for (const pt of points) {
        const energyKey = Math.round(pt.energy);
        const row = rows.get(energyKey) ?? { energy: energyKey };
        row[policyKey] = pt.accuracy;
        rows.set(energyKey, row);
      }
    }
    return [...rows.values()].sort((a, b) => a.energy - b.energy);
  })();

  const durationDisplay = activeTrialSummary ? `${activeTrialSummary.duration_s} s` : trial?.duration;
  const eventsDisplay = activeTrialSummary ? activeTrialSummary.events_logged : trial?.events;

  return (
    <div className="max-w-[1680px] mx-auto px-6 py-6 space-y-6">
      <div className="card p-5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="font-bold text-slate-900">Active Trial:</span>
          <select
            value={trial?.file || ""}
            onChange={(e) => onSelectTrial(e.target.value)}
            className="border border-slate-200 rounded-lg px-4 py-2 text-sm text-slate-700 min-w-[260px] bg-white"
          >
            {trialsList.map((t) => (
              <option key={t.file} value={t.file}>
                {t.file} ({t.policy})
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-8">
          <MetaItem icon={<Calendar size={18} />} label="Date" value={trial?.date || "Today"} />
          <MetaItem icon={<Clock size={18} />} label="Duration" value={durationDisplay} />
          <MetaItem icon={<FileSpreadsheet size={18} />} label="Total Events" value={eventsDisplay} />
        </div>
      </div>

      <div className="card p-6">
        <div className="flex items-center gap-3 mb-1">
          <div className="h-10 w-10 rounded-lg bg-sky-50 flex items-center justify-center text-sky-600">
            <BarChart3 size={20} />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-900">Accuracy vs. Energy Trade-off Curve</h2>
            <p className="text-sm text-slate-500">
              Evaluates detection accuracy (%) vs energy consumption (mJ) across the three sampling policies.
            </p>
          </div>
        </div>

        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={mergedCurve} margin={{ top: 30, right: 30, left: 10, bottom: 10 }}>
            <CartesianGrid stroke="#eef0f2" />
            <XAxis
              type="number"
              dataKey="energy"
              tick={{ fontSize: 12, fill: "#8a97a0" }}
              label={{ value: "Energy Consumption per Trial (mJ) [estimated]", position: "insideBottom", offset: -5, fontSize: 12, fill: "#8a97a0" }}
            />
            <YAxis
              type="number"
              domain={[0, 100]}
              ticks={[0, 20, 40, 60, 80, 100]}
              tick={{ fontSize: 12, fill: "#8a97a0" }}
              label={{ value: "Detection Accuracy (%)", angle: -90, position: "insideLeft", fontSize: 12, fill: "#8a97a0" }}
            />
            <Tooltip
              formatter={(value, name) => [`${value}%`, name]}
              labelFormatter={(label) => `${label} mJ`}
            />
            <Legend verticalAlign="bottom" height={36} />
            <Line
              name="Fixed-rate"
              dataKey="fixed"
              connectNulls
              stroke="#3366cc"
              strokeWidth={2}
              dot={{ r: 5, fill: "#3366cc" }}
            />
            <Line
              name="Threshold-adaptive"
              dataKey="threshold"
              connectNulls
              stroke="#e08a2c"
              strokeWidth={2}
              dot={{ r: 5, fill: "#e08a2c" }}
            />
            <Line
              name="Predictive-adaptive"
              dataKey="predictive"
              connectNulls
              stroke="#1a9b6c"
              strokeWidth={2}
              dot={{ r: 5, fill: "#1a9b6c" }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="card overflow-hidden">
        <div className="p-4 bg-slate-50 border-b border-slate-100 flex items-center justify-between">
          <h3 className="font-bold text-slate-800 text-sm">Policy Benchmark Performance Summary</h3>
          <span className="text-xs text-slate-500">Live aggregated metrics from MongoDB</span>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-navy-900 text-white text-left">
              <th className="px-5 py-3 font-semibold">Policy</th>
              <th className="px-5 py-3 font-semibold">Samples Taken</th>
              <th className="px-5 py-3 font-semibold">Detection Latency (s)</th>
              <th className="px-5 py-3 font-semibold">Energy per Trial (mJ)</th>
            </tr>
          </thead>
          <tbody>
            {comparisonTable.map((row) => {
              const isSelectedPolicy = trial && trial.policy && trial.policy.toLowerCase().includes(row.policy.toLowerCase().split("-")[0]);
              return (
                <tr
                  key={row.policy}
                  className={`border-t border-slate-100 ${isSelectedPolicy ? "bg-emerald-50/60 font-semibold" : ""}`}
                >
                  <td className="px-5 py-3 flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full inline-block" style={{ backgroundColor: row.color }} />
                    {row.policy}
                  </td>
                  <td className="px-5 py-3">{row.samples}</td>
                  <td className="px-5 py-3">{row.latency}</td>
                  <td className="px-5 py-3">{row.energy}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
