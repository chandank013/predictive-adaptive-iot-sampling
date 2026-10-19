import React from "react";
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
import { trialHistory, tradeoffCurve, policyComparisonTable } from "../data/mockData";

// Recharts matches multiple <Line data=...> arrays by array POSITION, not by x-value,
// which made the tooltip report the wrong energy for 2 of the 3 series. Merging every
// point into ONE dataset keyed by energy fixes it: each x belongs to the series that
// actually measured it, and the tooltip only shows series that have a value there.
const mergedCurve = (() => {
  const rows = new Map();
  for (const [policyKey, points] of Object.entries(tradeoffCurve)) {
    for (const pt of points) {
      const row = rows.get(pt.energy) ?? { energy: pt.energy };
      row[policyKey] = pt.accuracy;
      rows.set(pt.energy, row);
    }
  }
  return [...rows.values()].sort((a, b) => a.energy - b.energy);
})();

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
  // Meta info comes from the selected trial's row in the trial history, so the
  // dropdown (and the History page's "View" button) genuinely change what's shown.
  const trial = trialHistory.find((t) => t.file === selectedTrial) ?? trialHistory[0];

  return (
    <div className="max-w-[1680px] mx-auto px-6 py-6 space-y-6">
      <div className="card p-5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="font-bold text-slate-900">Trial:</span>
          <select
            value={trial.file}
            onChange={(e) => onSelectTrial(e.target.value)}
            className="border border-slate-200 rounded-lg px-4 py-2 text-sm text-slate-700 min-w-[220px]"
          >
            {trialHistory.map((t) => (
              <option key={t.file} value={t.file}>
                {t.file}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-8">
          <MetaItem icon={<Calendar size={18} />} label="Date" value={trial.date} />
          <MetaItem icon={<Clock size={18} />} label="Duration" value={trial.duration} />
          <MetaItem icon={<FileSpreadsheet size={18} />} label="Total Events" value={trial.events} />
        </div>
      </div>

      <div className="card p-6">
        <div className="flex items-center gap-3 mb-1">
          <div className="h-10 w-10 rounded-lg bg-sky-50 flex items-center justify-center text-sky-600">
            <BarChart3 size={20} />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-900">Accuracy vs. Energy Trade-off Curve</h2>
            <p className="text-sm text-slate-500">Each point represents a different trigger sensitivity / sampling setting.</p>
          </div>
        </div>

        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={mergedCurve} margin={{ top: 30, right: 30, left: 0, bottom: 10 }}>
            <CartesianGrid stroke="#eef0f2" />
            <XAxis
              type="number"
              dataKey="energy"
              domain={[0, 500]}
              ticks={[0, 50, 100, 150, 200, 250, 300, 350, 400, 450, 500]}
              tick={{ fontSize: 12, fill: "#8a97a0" }}
              label={{ value: "Energy Consumption per Trial (mJ)", position: "insideBottom", offset: -5, fontSize: 12, fill: "#8a97a0" }}
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
            {policyComparisonTable.map((row) => {
              // Highlight the row for the selected trial's policy.
              const isSelectedPolicy = row.policy === trial.policy;
              return (
                <tr
                  key={row.policy}
                  className={`border-t border-slate-100 ${isSelectedPolicy ? "bg-green-50 font-bold" : ""}`}
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
