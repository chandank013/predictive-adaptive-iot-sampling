import React, { useState } from "react";
import Navbar from "./components/Navbar.jsx";
import Live from "./pages/Live.jsx";
import Results from "./pages/Results.jsx";
import History from "./pages/History.jsx";

export default function App() {
  const [activeTab, setActiveTab] = useState("Live Monitoring");
  const [selectedTrial, setSelectedTrial] = useState("predictive_run_03.csv");

  // Clicking "View" on a Trial History row jumps to Trial Results with that trial selected.
  function viewTrial(file) {
    setSelectedTrial(file);
    setActiveTab("Trial Results");
  }

  return (
    <div className="min-h-screen bg-[#eef2f5]">
      <Navbar activeTab={activeTab} onChangeTab={setActiveTab} />
      {activeTab === "Live Monitoring" && <Live />}
      {activeTab === "Trial Results" && (
        <Results selectedTrial={selectedTrial} onSelectTrial={setSelectedTrial} />
      )}
      {activeTab === "Trial History" && <History onViewTrial={viewTrial} />}
    </div>
  );
}
