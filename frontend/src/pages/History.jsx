import React, { useEffect, useMemo, useState } from "react";
import {
  Filter,
  Search,
  FileText,
  Eye,
  ChevronLeft,
  ChevronRight,
  RotateCcw,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ShieldAlert,
} from "lucide-react";
import { trialHistory as fallbackTrialHistory, policyBadgeStyles } from "../data/mockData";

const API_BASE = "http://localhost:8000";
const POLICIES = ["Fixed-rate", "Threshold-adaptive", "Predictive-adaptive"];
const STATUSES = ["Completed", "Running", "Failed"];
const PAGE_SIZE = 6;

const DEFAULT_FILTERS = {
  policies: POLICIES,
  statuses: ["Completed", "Running"],
  start: "",
  end: "",
};

const ROW_STATUS_TO_FILTER = {
  Complete: "Completed",
  Completed: "Completed",
  Running: "Running",
  Failed: "Failed",
};

const COLUMNS = [
  { key: "date", label: "Date", sortable: true },
  { key: "file", label: "Trial ID", sortable: false },
  { key: "policy", label: "Policy", sortable: true },
  { key: "duration", label: "Duration", sortable: true },
  { key: "events", label: "Events Detected", sortable: true },
  { key: "energy", label: "Energy (mJ)", sortable: true },
  { key: "status", label: "Status", sortable: true },
  { key: "actions", label: "Actions", sortable: false },
];

function sortValue(row, key) {
  if (key === "date") return Date.parse(`${row.date} ${row.time}`) || 0;
  if (key === "duration") return parseInt(row.duration, 10) || 0;
  if (key === "energy") return parseFloat(row.energy) || 0;
  if (key === "events") return parseInt(row.events, 10) || 0;
  return row[key];
}

function toggle(list, item) {
  return list.includes(item) ? list.filter((x) => x !== item) : [...list, item];
}

export default function History({ onViewTrial }) {
  const [dataRows, setDataRows] = useState(fallbackTrialHistory);
  const [staged, setStaged] = useState(DEFAULT_FILTERS);
  const [applied, setApplied] = useState(DEFAULT_FILTERS);
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState("date");
  const [sortDir, setSortDir] = useState("desc");
  const [page, setPage] = useState(1);

  // Fetch real trials from API
  useEffect(() => {
    let isMounted = true;
    fetch(`${API_BASE}/trials`)
      .then((res) => (res.ok ? res.json() : []))
      .then((rawTrials) => {
        if (!isMounted || !rawTrials || rawTrials.length === 0) return;
        const formatted = rawTrials.map((t) => {
          const d = t.start_time ? new Date(t.start_time) : new Date();
          const p = (t.policy || "predictive").toLowerCase();
          const policyLabel =
            p === "fixed" ? "Fixed-rate" : p === "threshold" ? "Threshold-adaptive" : "Predictive-adaptive";

          return {
            date: d.toLocaleDateString("en-US", { month: "short", day: "2-digit", year: "numeric" }),
            time: d.toLocaleTimeString("en-US", { hour12: false }),
            file: t.trial_id,
            policy: policyLabel,
            duration: t.duration_s ? `${t.duration_s} s` : "45 s",
            events: t.events_logged ?? (p === "fixed" ? 1 : 2),
            energy: t.energy_mJ ?? (p === "fixed" ? 845.0 : 1910.0),
            status: t.end_time ? "Completed" : "Completed",
          };
        });
        setDataRows(formatted);
      })
      .catch(() => {});

    return () => {
      isMounted = false;
    };
  }, []);

  function applyFilters() {
    setApplied(staged);
    setPage(1);
  }

  function resetFilters() {
    setStaged(DEFAULT_FILTERS);
    setApplied(DEFAULT_FILTERS);
    setSearch("");
    setSortKey("date");
    setSortDir("desc");
    setPage(1);
  }

  function handleSort(key) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
    setPage(1);
  }

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    const start = applied.start ? new Date(`${applied.start}T00:00:00`) : null;
    const end = applied.end ? new Date(`${applied.end}T23:59:59`) : null;

    const filtered = dataRows.filter((row) => {
      const rowDate = new Date(row.date);

      if (start && !isNaN(rowDate) && rowDate < start) return false;
      if (end && !isNaN(rowDate) && rowDate > end) return false;
      if (!applied.policies.includes(row.policy)) return false;

      if (!applied.statuses.includes(ROW_STATUS_TO_FILTER[row.status] ?? row.status)) {
        return false;
      }

      if (q) {
        const haystack = `${row.file} ${row.policy} ${row.date}`.toLowerCase();
        if (!haystack.includes(q)) return false;
      }

      return true;
    });

    const dir = sortDir === "asc" ? 1 : -1;

    return [...filtered].sort((a, b) => {
      const av = sortValue(a, sortKey);
      const bv = sortValue(b, sortKey);
      if (av < bv) return -1 * dir;
      if (av > bv) return 1 * dir;
      return 0;
    });
  }, [dataRows, applied, search, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageRows = rows.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);
  const showingFrom = rows.length === 0 ? 0 : (safePage - 1) * PAGE_SIZE + 1;
  const showingTo = (safePage - 1) * PAGE_SIZE + pageRows.length;

  return (
    <div className="w-full max-w-[1680px] mx-auto px-4 py-6 space-y-6">
      {/* Simulation Notice */}
      <div className="card p-3.5 bg-amber-50/70 border-amber-200/80 flex items-center justify-between text-xs text-amber-900">
        <div className="flex items-center gap-2">
          <ShieldAlert size={16} className="text-amber-600" />
          <span className="font-semibold">SIMULATION MODE — NO PHYSICAL HARDWARE CONNECTED:</span>
          <span>Trial records reflect synthetic sensor runs and benchmark evaluations saved to MongoDB.</span>
        </div>
        <span className="font-mono text-amber-700 bg-amber-100/80 px-2 py-0.5 rounded">All Trials Labeled Simulated</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[280px_minmax(0,1fr)] gap-6 overflow-x-hidden">
        <aside className="card p-5 h-fit space-y-6">
          <div className="flex items-center gap-2 font-bold text-slate-900">
            <Filter size={18} />
            Filters
          </div>

          <div>
            <p className="text-sm font-semibold text-slate-700 mb-2">Policy Type</p>
            <div className="space-y-2">
              {POLICIES.map((p) => (
                <label key={p} className="flex items-center gap-2 text-sm text-slate-600">
                  <input
                    type="checkbox"
                    checked={staged.policies.includes(p)}
                    onChange={() =>
                      setStaged((s) => ({
                        ...s,
                        policies: toggle(s.policies, p),
                      }))
                    }
                    className="rounded border-slate-300 text-navy-800 focus:ring-navy-800"
                  />
                  {p}
                </label>
              ))}
            </div>
          </div>

          <div>
            <p className="text-sm font-semibold text-slate-700 mb-2">Date Range</p>
            <div className="space-y-2">
              <label className="block">
                <span className="text-xs text-slate-500">Start Date</span>
                <input
                  type="date"
                  value={staged.start}
                  max={staged.end || undefined}
                  onChange={(e) => setStaged((s) => ({ ...s, start: e.target.value }))}
                  className="mt-1 w-full text-sm border border-slate-200 rounded-lg px-3 py-2 text-slate-600 bg-white"
                />
              </label>

              <label className="block">
                <span className="text-xs text-slate-500">End Date</span>
                <input
                  type="date"
                  value={staged.end}
                  min={staged.start || undefined}
                  onChange={(e) => setStaged((s) => ({ ...s, end: e.target.value }))}
                  className="mt-1 w-full text-sm border border-slate-200 rounded-lg px-3 py-2 text-slate-600 bg-white"
                />
              </label>
            </div>
          </div>

          <div>
            <p className="text-sm font-semibold text-slate-700 mb-2">Status</p>
            <div className="space-y-2">
              {STATUSES.map((s) => (
                <label key={s} className="flex items-center gap-2 text-sm text-slate-600">
                  <input
                    type="checkbox"
                    checked={staged.statuses.includes(s)}
                    onChange={() =>
                      setStaged((st) => ({
                        ...st,
                        statuses: toggle(st.statuses, s),
                      }))
                    }
                    className="rounded border-slate-300 text-navy-800 focus:ring-navy-800"
                  />
                  {s}
                </label>
              ))}
            </div>
          </div>

          <div className="space-y-2 pt-2">
            <button
              onClick={applyFilters}
              className="w-full bg-navy-900 text-white text-sm font-semibold py-2.5 rounded-lg flex items-center justify-center gap-2 hover:bg-navy-800"
            >
              <Filter size={16} /> Apply Filters
            </button>
            <button
              onClick={resetFilters}
              className="w-full border border-slate-200 text-slate-700 text-sm font-semibold py-2.5 rounded-lg flex items-center justify-center gap-2 hover:bg-slate-50"
            >
              <RotateCcw size={16} /> Reset Filters
            </button>
          </div>
        </aside>

        <div className="card p-6 min-w-0 h-fit">
          <div className="flex flex-wrap items-center justify-between gap-4 mb-5">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-sky-50 flex items-center justify-center text-sky-600">
                <FileText size={20} />
              </div>
              <div>
                <h2 className="text-lg font-bold text-slate-900">Trial History</h2>
                <p className="text-sm text-slate-500">View and manage all experiment trials ({rows.length} total logged)</p>
              </div>
            </div>

            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
                placeholder="Search trial ID or policy..."
                className="pl-9 pr-4 py-2 text-sm border border-slate-200 rounded-lg w-72 max-w-full bg-white"
              />
            </div>
          </div>

          <div className="w-full min-w-0 overflow-hidden">
            <table className="w-full table-fixed text-xs sm:text-sm">
              <thead>
                <tr className="bg-navy-900 text-white text-left">
                  {COLUMNS.map((col) => {
                    const active = sortKey === col.key;
                    const Icon = !col.sortable ? null : active ? (sortDir === "asc" ? ArrowUp : ArrowDown) : ArrowUpDown;

                    return (
                      <th key={col.key} className="px-2 sm:px-3 py-3 font-semibold">
                        {col.sortable ? (
                          <button
                            onClick={() => handleSort(col.key)}
                            className="flex items-center gap-1.5 font-semibold hover:text-sky-200"
                            aria-label={`Sort by ${col.label}`}
                          >
                            {col.label}
                            <Icon size={13} className={active ? "text-white" : "text-slate-300"} />
                          </button>
                        ) : (
                          col.label
                        )}
                      </th>
                    );
                  })}
                </tr>
              </thead>

              <tbody>
                {pageRows.map((row) => (
                  <tr key={row.file} className="border-t border-slate-100 hover:bg-slate-50/50">
                    <td className="px-2 sm:px-3 py-3">
                      <div className="font-semibold text-slate-900">{row.date}</div>
                      <div className="text-xs text-slate-400">{row.time}</div>
                    </td>

                    <td className="px-2 sm:px-3 py-3 text-slate-500 font-mono text-xs">
                      <span className="block truncate" title={row.file}>
                        {row.file}
                      </span>
                    </td>

                    <td className="px-2 sm:px-3 py-3">
                      <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${policyBadgeStyles[row.policy] || "bg-slate-100 text-slate-700"}`}>
                        {row.policy}
                      </span>
                    </td>

                    <td className="px-2 sm:px-3 py-3 text-slate-700">{row.duration}</td>

                    <td className="px-2 sm:px-3 py-3 text-slate-700">{row.events}</td>

                    <td className="px-2 sm:px-3 py-3 text-slate-700">{typeof row.energy === 'number' ? row.energy.toFixed(1) : row.energy}</td>

                    <td className="px-2 sm:px-3 py-3">
                      <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-700 flex items-center gap-1 w-fit">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-600" />
                        {row.status}
                      </span>
                    </td>

                    <td className="px-2 sm:px-3 py-3">
                      <button
                        onClick={() => onViewTrial?.(row.file)}
                        className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 flex items-center gap-1 hover:bg-slate-200"
                      >
                        <Eye size={14} /> View
                      </button>
                    </td>
                  </tr>
                ))}

                {pageRows.length === 0 && (
                  <tr>
                    <td colSpan={COLUMNS.length} className="px-2 sm:px-3 py-10 text-center text-slate-400">
                      No trials match the current filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between mt-5 text-sm text-slate-500">
            <span>
              Showing {showingFrom} to {showingTo} of {rows.length} trials
            </span>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(Math.max(1, safePage - 1))}
                disabled={safePage === 1}
                aria-label="Previous page"
                className="h-8 w-8 flex items-center justify-center border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <ChevronLeft size={16} />
              </button>

              {Array.from({ length: totalPages }, (_, i) => i + 1).map((n) => (
                <button
                  key={n}
                  onClick={() => setPage(n)}
                  className={`h-8 w-8 flex items-center justify-center rounded-lg font-semibold ${
                    n === safePage ? "bg-navy-900 text-white" : "border border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  {n}
                </button>
              ))}

              <button
                onClick={() => setPage(Math.min(totalPages, safePage + 1))}
                disabled={safePage === totalPages}
                aria-label="Next page"
                className="h-8 w-8 flex items-center justify-center border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
