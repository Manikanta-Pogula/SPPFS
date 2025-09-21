// frontend/src/pages/FacultyDashboard.jsx
import React from "react";
import { useNavigate } from "react-router-dom";

/*
  FacultyDashboard: Menu-only layout.
  - No branch/year/semester quick-action here (removed).
  - "Open" buttons navigate; Graph Analysis sets a default batch.
*/

export default function FacultyDashboard() {
  const navigate = useNavigate();

  const defaultBatch = (typeof window !== "undefined" && window.SELECTED_BATCH) || {
    branch: "CS",
    year: 2024,
    semester: 4,
  };

  function openRoute(path, opts = {}) {
    if (opts.batch) {
      window.SELECTED_BATCH = opts.batch;
    } else if (!window.SELECTED_BATCH) {
      window.SELECTED_BATCH = defaultBatch;
    }
    navigate(path);
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Faculty Dashboard</h1>
        <p className="text-sm text-slate-500">Quick actions and links for faculty</p>
      </div>

      <div className="grid gap-6">
        <div className="bg-white p-4 rounded shadow-sm">
          <h3 className="text-lg font-medium">Data Upload</h3>
          <p className="text-sm text-slate-600">Upload CSV or manual entry</p>
          <div className="mt-3">
            <button
              onClick={() => openRoute("/uploads")}
              className="px-3 py-1 bg-slate-100 rounded text-sm"
            >
              Open
            </button>
          </div>
        </div>

        <div className="bg-white p-4 rounded shadow-sm">
          <h3 className="text-lg font-medium">Student Report</h3>
          <p className="text-sm text-slate-600">View & analyze student reports</p>
          <div className="mt-3">
            <button
              onClick={() => openRoute("/student-report")}
              className="px-3 py-1 bg-slate-100 rounded text-sm"
            >
              Open
            </button>
          </div>
        </div>

        <div className="bg-white p-4 rounded shadow-sm">
          <h3 className="text-lg font-medium">Results Search</h3>
          <p className="text-sm text-slate-600">Search results by PIN / batch</p>
          <div className="mt-3">
            <button
              onClick={() => openRoute("/results-search")}
              className="px-3 py-1 bg-slate-100 rounded text-sm"
            >
              Open
            </button>
          </div>
        </div>

        <div className="bg-white p-4 rounded shadow-sm">
          <h3 className="text-lg font-medium">Graph Analysis</h3>
          <p className="text-sm text-slate-600">View graphs and progress cards</p>
          <div className="mt-3">
            <button
              onClick={() => openRoute("/graph-analysis", { batch: defaultBatch })}
              className="px-3 py-1 bg-indigo-600 text-white rounded text-sm"
            >
              Open
            </button>
          </div>
        </div>

        <div className="bg-white p-4 rounded shadow-sm">
          <h3 className="text-lg font-medium">Uploaded Files</h3>
          <p className="text-sm text-slate-600">Manage uploaded files</p>
          <div className="mt-3">
            <button
              onClick={() => openRoute("/uploaded-files")}
              className="px-3 py-1 bg-slate-100 rounded text-sm"
            >
              Open
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
