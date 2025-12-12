// src/App.jsx
import React from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";
import GraphAnalysis from "./components/GraphAnalysis";
import ResultsSearch from "./pages/ResultsSearch";

export default function App() {
  return (
    <Router>
      {/* App shell background */}
      <div className="min-h-screen bg-slate-100 text-slate-900">
        {/* No top navbar here – GraphAnalysis shows its own welcome + PDF button */}
        <div className="p-4 md:p-6">
          <Routes>
            {/* Default redirect to Graph Analysis */}
            <Route path="/" element={<Navigate to="/graph" />} />

            {/* Graph Analysis Page */}
            <Route
              path="/graph"
              element={
                <GraphAnalysis
                  branch="CS"
                  year={2024}
                  semester={4}
                  facultyName="Faculty"
                />
              }
            />

            {/* Results Search Page */}
            <Route path="/results" element={<ResultsSearch />} />
          </Routes>
        </div>
      </div>
    </Router>
  );
}
