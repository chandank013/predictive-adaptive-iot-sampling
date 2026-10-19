// Mock data standing in for live MQTT / MongoDB-backed data.
// Replace with real API calls once backend/api/server.py is running
// (see PROTOTYPE_PLAN.md, Phase 3).

// ---------- Live Monitoring ----------
function generateLiveSeries() {
  const points = [];
  for (let t = 0; t <= 60; t++) {
    let value = 0.12 + Math.sin(t * 1.3) * 0.03 + Math.random() * 0.03;
    if (t >= 28 && t < 37) {
      const frac = (t - 28) / 9;
      value += frac * 0.55;
    } else if (t >= 37 && t <= 44) {
      value = 1.35 + Math.sin(t * 3) * 0.25 + Math.random() * 0.1;
    } else if (t > 44 && t <= 48) {
      const frac = 1 - (t - 44) / 4;
      value = 0.12 + 0.6 * Math.max(frac, 0) + Math.random() * 0.03;
    }
    points.push({ t, value: Number(value.toFixed(3)) });
  }
  return points;
}

export const liveVibrationSeries = generateLiveSeries();
export const eventWindow = { start: 37, end: 44 };
export const threshold = 1.0;

export const energySparkline = Array.from({ length: 20 }, (_, i) => ({
  i,
  value: 30 + Math.random() * 25,
}));

export const liveStats = {
  activePolicy: "Predictive",
  samplingInterval: "100 ms",
  samplingMode: "High Rate",
  energyDraw: "42.3 mA",
  currentVibration: "0.28 g",
  vibrationChange: "58% from peak",
  samplingRate: "10.0 Hz",
  samplingRateSub: "(100 ms)",
  packetsSent: "3,142",
  packetsSentSub: "(this session)",
  uptime: "00:12:36",
  uptimeSub: "(current trial)",
};

export const eventLog = [
  { id: 1, type: "event", text: "Event detected \u2014 vibration crossed threshold", time: "14:32:08" },
  { id: 2, type: "ok", text: "Sampling rate increased to 100 ms", time: "14:32:08" },
  { id: 3, type: "info", text: "Prediction: Event likely soon", time: "14:32:07" },
  { id: 4, type: "warn", text: "Vibration rising (0.82 g)", time: "14:32:06" },
  { id: 5, type: "ok", text: "Normal condition", time: "14:31:50" },
  { id: 6, type: "event", text: "Event ended \u2014 back to low sampling rate", time: "14:31:20" },
  { id: 7, type: "ok", text: "Sampling rate decreased to 1 s", time: "14:31:20" },
];

// ---------- Trial Results ----------
export const trialResultsMeta = {
  trialFile: "predictive_run_03.csv",
  date: "Oct 04, 2026",
  duration: "10 min",
  totalEvents: 8,
};

export const tradeoffCurve = {
  fixed: [
    { energy: 300, accuracy: 52 },
    { energy: 350, accuracy: 68 },
    { energy: 400, accuracy: 80 },
    { energy: 450, accuracy: 85 },
    { energy: 500, accuracy: 90 },
  ],
  threshold: [
    { energy: 120, accuracy: 65 },
    { energy: 150, accuracy: 80 },
    { energy: 200, accuracy: 85 },
    { energy: 240, accuracy: 88 },
    { energy: 275, accuracy: 90 },
  ],
  predictive: [
    { energy: 40, accuracy: 64 },
    { energy: 70, accuracy: 78 },
    { energy: 100, accuracy: 87 },
    { energy: 140, accuracy: 91 },
    { energy: 175, accuracy: 93 },
  ],
};

export const policyComparisonTable = [
  { policy: "Fixed-rate", color: "#3366cc", samples: "12,000", latency: "0.52", energy: "480.5" },
  { policy: "Threshold-adaptive", color: "#e08a2c", samples: "4,320", latency: "0.28", energy: "210.3" },
  { policy: "Predictive-adaptive", color: "#1a9b6c", samples: "2,150", latency: "0.18", energy: "126.7", highlight: true },
];

// ---------- Trial History ----------
export const trialHistory = [
  { date: "Oct 04, 2026", time: "14:32:10", file: "predictive_run_03.csv", policy: "Predictive-adaptive", duration: "10 min", events: 5, energy: 42.3, status: "Complete" },
  { date: "Oct 04, 2026", time: "12:18:27", file: "threshold_run_02.csv", policy: "Threshold-adaptive", duration: "10 min", events: 4, energy: 68.1, status: "Complete" },
  { date: "Oct 04, 2026", time: "10:05:14", file: "fixed_run_01.csv", policy: "Fixed-rate", duration: "10 min", events: 4, energy: 112.5, status: "Complete" },
  { date: "Oct 03, 2026", time: "16:45:03", file: "predictive_run_02.csv", policy: "Predictive-adaptive", duration: "15 min", events: 8, energy: 40.7, status: "Complete" },
  { date: "Oct 03, 2026", time: "13:22:19", file: "threshold_run_01.csv", policy: "Threshold-adaptive", duration: "15 min", events: 7, energy: 66.9, status: "Complete" },
  { date: "Oct 03, 2026", time: "11:10:05", file: "fixed_run_02.csv", policy: "Fixed-rate", duration: "15 min", events: 6, energy: 118.4, status: "Complete" },
  { date: "Oct 02, 2026", time: "17:30:41", file: "predictive_run_01.csv", policy: "Predictive-adaptive", duration: "10 min", events: 5, energy: 44.1, status: "Complete" },
  { date: "Oct 02, 2026", time: "14:12:33", file: "fixed_run_01_repeat.csv", policy: "Fixed-rate", duration: "10 min", events: 4, energy: 115.8, status: "Complete" },
];

export const policyBadgeStyles = {
  "Fixed-rate": "bg-blue-100 text-blue-700",
  "Threshold-adaptive": "bg-orange-100 text-orange-700",
  "Predictive-adaptive": "bg-green-100 text-green-700",
};
