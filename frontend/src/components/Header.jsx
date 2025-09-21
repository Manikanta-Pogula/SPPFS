// frontend/src/components/Header.jsx
import React from "react";
import { useNavigate } from "react-router-dom";

/**
 * Minimal common header used across pages.
 * - No page-specific nav links here (keeps it clean)
 * - Shows app title, welcome + logout (same on every page)
 */
export default function Header() {
  const navigate = useNavigate();
  const facultyName = (typeof window !== "undefined" && window.FACULTY_NAME) || "Faculty";

  function handleLogout() {
    // TODO: call backend logout endpoint when auth is implemented
    // For now just navigate to home/dashboard
    navigate("/dashboard");
  }

  return (
    <header className="bg-white border-b">
      <div className="container mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="text-lg font-semibold">🎓 Student Performance System</div>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-sm text-slate-700">
            Welcome back, <strong>{facultyName}</strong>
          </div>
          <button
            onClick={handleLogout}
            className="px-3 py-1 bg-red-50 text-red-700 rounded border text-sm"
          >
            Logout
          </button>
        </div>
      </div>
    </header>
  );
}
