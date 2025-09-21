// src/App.jsx
import React from "react";
import GraphAnalysis from "./components/GraphAnalysis";

export default function App() {
  // For dev you can pass props directly (or rely on server to set window.SELECTED_BATCH)
  return (
    <div className="app-container">
      {/* Example: for quick local testing pass branch/year/semester here */}
      <GraphAnalysis branch="CS" year={2024} semester={4} facultyName="Dr. Faculty" />
    </div>
  );
}
