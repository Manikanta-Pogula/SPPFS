// src/App.jsx
import React from "react";
import { BrowserRouter as Router, Routes, Route, Link, Navigate } from "react-router-dom";
import GraphAnalysis from "./components/GraphAnalysis";
import ResultsSearch from "./pages/ResultsSearch";

export default function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-100 text-gray-900">
        {/* Top Navigation Bar */}
        <nav className="bg-white shadow p-4 flex justify-between items-center">
          <h1 className="text-lg font-semibold">🎓 Faculty Dashboard</h1>
          <div className="space-x-4">
            <Link to="/graph" className="text-blue-600 hover:underline">
              Graph Analysis
            </Link>
            <Link to="/results" className="text-blue-600 hover:underline">
              Results Search
            </Link>
          </div>
        </nav>

        {/* Route Views */}
        <div className="p-6">
          <Routes>
            {/* Default redirect to Graph Analysis */}
            <Route path="/" element={<Navigate to="/graph" />} />

            {/* Graph Analysis Page */}
            <Route
              path="/graph"
              element={<GraphAnalysis branch="CS" year={2024} semester={4} facultyName="Dr. Faculty" />}
            />

            {/* Results Search Page */}
            <Route path="/results" element={<ResultsSearch />} />
          </Routes>
        </div>
      </div>
    </Router>
  );
}
