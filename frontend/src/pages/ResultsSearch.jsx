// frontend/src/pages/ResultsSearch.jsx
import React, { useState, useEffect, useMemo } from "react";
import "./ResultsSearch.css";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from "recharts";

/**
 * ResultsSearch Page
 *
 * Fetches:
 *  - GET /api/results/search?pin=...   (returns student, semesters[], trend[])
 *  - GET /api/results/overview?branch=...&year=...&semester=...  (optional for class average)
 *
 * Notes:
 *  - Uses fetch(..., { credentials: 'include' }) so that cookies/sessions are sent.
 *  - For dev mode (React dev server at port 3000), add "proxy": "http://127.0.0.1:5000" to package.json
 *    to forward API requests to Flask backend.
 */

function gradeFromScore(score) {
  if (score === null || score === undefined) return "N/A";
  if (score >= 90) return "A+";
  if (score >= 80) return "A";
  if (score >= 70) return "B";
  if (score >= 60) return "C";
  if (score >= 50) return "D";
  return "F";
}

function passFailFromScore(score) {
  if (score === null || score === undefined) return "❌ Fail";
  return score >= 40 ? "✅ Pass" : "❌ Fail";
}

function prettyNumber(v) {
  if (v === null || v === undefined) return "-";
  if (typeof v === "number") return Number.isInteger(v) ? v.toString() : v.toFixed(2);
  const n = Number(v);
  return Number.isNaN(n) ? String(v) : (Number.isInteger(n) ? String(n) : n.toFixed(2));
}

export default function ResultsSearch() {
  const [pin, setPin] = useState("");
  const [recent, setRecent] = useState([]);
  const [student, setStudent] = useState(null);
  const [loggedUser, setLoggedUser] = useState(null);
  const [semesters, setSemesters] = useState([]); // [{semester, subjects:[], overall_score, risk}, ...]
  const [trend, setTrend] = useState([]); // [{semester, overall_score}, ...]
  const [selectedSem, setSelectedSem] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showClassAvg, setShowClassAvg] = useState(false);
  const [classAverages, setClassAverages] = useState([]); // per-sem class average
  const [fetchingClassAvg, setFetchingClassAvg] = useState(false);


  // load recent searches from localStorage
  useEffect(() => {
    try {
      const raw = localStorage.getItem("recentResultsSearches");
      if (raw) setRecent(JSON.parse(raw).slice(0, 5));
    } catch (e) {
      setRecent([]);
    }
  }, []);

  // fetch logged-in faculty info for header
  useEffect(() => {
    async function fetchUser() {
      try {
        const res = await fetch("/api/results/me", {
          credentials: "include",
          headers: { "Accept": "application/json" },
        });
        if (res.ok) {
          const data = await res.json();
          setLoggedUser(data);
        }
      } catch (e) {
        console.warn("Failed to load current user", e);
      }
    }
    fetchUser();
  }, []);


  // save recent
  function pushRecent(pinVal) {
    try {
      const arr = [...(JSON.parse(localStorage.getItem("recentResultsSearches") || "[]"))];
      const normalized = String(pinVal || "").trim();
      if (!normalized) return;
      // put unique most-recent-first
      const filtered = arr.filter(x => x !== normalized);
      filtered.unshift(normalized);
      const top = filtered.slice(0, 5);
      localStorage.setItem("recentResultsSearches", JSON.stringify(top));
      setRecent(top);
    } catch (e) {
      // ignore
    }
  }

  // Fetch search result for PIN (fetch full student JSON; backend returns semesters + trend)
// --- replace the existing doSearch(...) in frontend/src/pages/ResultsSearch.jsx with this ---
async function doSearch(pinValue) {
  setError(null);
  const p = String(pinValue || "").trim();
  if (!p) {
    setError("Please enter a PIN.");
    return;
  }
  setLoading(true);
  setStudent(null);
  setSemesters([]);
  setTrend([]);
  setSelectedSem(null);
  setClassAverages([]);

  try {
    // 1) main search call
    const resp = await fetch(`/api/results/search?pin=${encodeURIComponent(p)}`, {
      method: "GET",
      credentials: "include",
      headers: { "Accept": "application/json" }
    });

    if (!resp.ok) {
      const txt = await resp.text();
      throw new Error(`Server returned ${resp.status}: ${txt}`);
    }

    const json = await resp.json();
    // top-level student info
    setStudent(json.student || null);

    // 2) Normalize backend response:
    // Backend may return either:
    //  - json.semesters (array)  <-- new/desired shape
    //  - json.marks_by_semester (object: { "1": [...], "4": [...] }) <-- older shape
    // Convert any legacy shape to the "semesters" array expected by this UI.

    let sems = [];
    if (Array.isArray(json.semesters) && json.semesters.length > 0) {
      sems = json.semesters.map(s => ({
        semester: Number(s.semester),
        subjects: s.subjects || s.subjects || [],
        overall_score: s.overall_score ?? null,
        feedback: s.feedback ?? null
      }));
    } else if (json.marks_by_semester && typeof json.marks_by_semester === "object") {
      // convert map -> array
      const keys = Object.keys(json.marks_by_semester).sort((a,b)=>Number(a)-Number(b));
      sems = keys.map(k => {
        const rows = json.marks_by_semester[k] || [];
        const subjects = rows.map(r => {
          const subjScore = (typeof r.subject_score !== "undefined") ? r.subject_score : null;
          return {
            sub_code: r.sub_code || r.sub_code || "UNKNOWN",
            sub_name: r.sub_name || r.sub_code || "Unknown subject",
            mid1: (typeof r.mid1 !== "undefined") ? r.mid1 : null,
            mid2: (typeof r.mid2 !== "undefined") ? r.mid2 : null,
            internal: (typeof r.internal !== "undefined") ? r.internal : null,
            end_sem: (typeof r.end_sem !== "undefined") ? r.end_sem : null,
            total: (typeof r.total !== "undefined") ? r.total : null,
            attendance: (typeof r.attendance !== "undefined") ? r.attendance : null,
            subject_score: subjScore,
            risk: r.risk || null,
            grade: r.grade || gradeFromScore(subjScore),
            result: r.result || passFailFromScore(subjScore)
          };
        });
        return { semester: Number(k), subjects, overall_score: null, feedback: null };
      });
    } else {
      sems = [];
    }

    setSemesters(sems);

    // choose sensible default selected semester:
    const firstWithData = sems.find(s => Array.isArray(s.subjects) && s.subjects.length > 0);
    const semDefault = firstWithData ? firstWithData.semester : (sems.length ? sems[0].semester : 1);
    setSelectedSem(semDefault);

    pushRecent(p);

    // 3) fetch trend (SGPA/overall trend) from backend graph endpoint (backend already exposes this)
    try {
      const trendResp = await fetch(`/api/results/graphs/sgpa_trend?pin=${encodeURIComponent(p)}`, {
        method: "GET",
        credentials: "include",
        headers: { "Accept": "application/json" }
      });
      if (trendResp.ok) {
        const tjson = await trendResp.json();
        // backend returns { student: {...}, trend: [{semester, overall_score}, ...] }
        if (Array.isArray(tjson.trend)) {
          setTrend(tjson.trend);
        } else if (Array.isArray(tjson.data)) {
          setTrend(tjson.data);
        } else {
          setTrend([]);
        }
      } else {
        // ignore non-OK trend fetch (we still show table)
        console.warn("Trend fetch returned", trendResp.status);
      }
    } catch (err) {
      console.warn("Trend fetch error", err);
    }

  } catch (err) {
    console.error("Search error", err);
    setError(err.message || "Search failed");
  } finally {
    setLoading(false);
  }
}


  // Quick handler for clicking recent searches
  function onRecentClick(pinVal) {
    setPin(pinVal);
    doSearch(pinVal);
  }

  // derived: list of semester numbers 1..6 and marks whether each has data
  const semInfo = useMemo(() => {
    const info = {};
    for (let i = 1; i <= 6; i++) info[i] = { hasData: false, index: -1 };
    semesters.forEach((s, idx) => {
      if (s && s.semester) {
        info[s.semester] = { hasData: true, index: idx };
      }
    });
    return info;
  }, [semesters]);

  // selected semester data
  const selectedSemData = useMemo(() => {
    if (!selectedSem || !semesters) return null;
    return semesters.find(s => Number(s.semester) === Number(selectedSem)) || null;
  }, [selectedSem, semesters]);

  // Toggle and (optionally) fetch class averages for each semester
  async function toggleClassAvg() {
    const next = !showClassAvg;
    setShowClassAvg(next);
    if (next && student) {
      // fetch overview per sem for branch/year - 1..6
      const branch = student.branch;
      const year = student.exam_year || student.year || student.class_year || null;
      if (!branch || !year) {
        setError("Cannot fetch class averages: student branch/year missing.");
        return;
      }
      setFetchingClassAvg(true);
      try {
        const promises = [];
        for (let sem = 1; sem <= 6; sem++) {
          promises.push(fetch(`/api/results/overview?branch=${encodeURIComponent(branch)}&year=${encodeURIComponent(year)}&semester=${sem}`, {
            credentials: "include"
          }).then(r => r.ok ? r.json() : null));  
        }
        const results = await Promise.all(promises);
        const avgs = results.map((res, idx) => {
          if (!res || typeof res.class_average === "undefined" || res.class_average === null) return null;
          return Number(res.class_average);
        });
        setClassAverages(avgs);
      } catch (err) {
        console.error("Class avg fetch error", err);
        setError("Failed to fetch class averages.");
      } finally {
        setFetchingClassAvg(false);
      }
    }
  }

  // build chart data for trend (semesters 1..6)
  const chartData = useMemo(() => {
    const arr = [];
    for (let sem = 1; sem <= 6; sem++) {
      const t = (trend || []).find(x => Number(x.semester) === sem);
      const studentVal = (t && (t.overall_score !== null && typeof t.overall_score !== "undefined")) ? Number(t.overall_score) : null;
      const classVal = (classAverages && classAverages.length >= sem) ? (classAverages[sem - 1] ?? null) : null;
      arr.push({
        semester: `Sem ${sem}`,
        student: studentVal,
        classAvg: classVal
      });
    }
    return arr;
  }, [trend, classAverages]);

  // compute overall for selected sem (prefers backend overall if present)
  const selectedOverall = selectedSemData ? selectedSemData.overall_score : null;

  // render subject rows for table
  function renderSubjectsTable() {
    if (!selectedSemData || !Array.isArray(selectedSemData.subjects) || selectedSemData.subjects.length === 0) {
      return <div className="no-records">❌ No records for this semester.</div>;
    }
    const rows = selectedSemData.subjects;
    return (
      <table className="rs-table">
        <thead>
          <tr>
            <th>Subject Code</th>
            <th>Subject Name</th>
            <th>Mid-1</th>
            <th>Mid-2</th>
            <th>Internal</th>
            <th>End Sem</th>
            <th>Subject Score</th>
            <th>Grade</th>
            <th>Result</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, idx) => {
            // backend may provide grade/result; fallback to local compute
            const subjScore = (r.subject_score !== undefined && r.subject_score !== null) ? Number(r.subject_score) : null;
            const grade = r.grade || gradeFromScore(subjScore);
            const result = r.result || passFailFromScore(subjScore);
            return (
              <tr key={idx}>
                <td>{r.sub_code || "-"}</td>
                <td>{r.sub_name || r.sub_code || "Unknown subject"}</td>
                <td className={r.mid1 === 0 ? "absent" : ""}>{r.mid1 === 0 ? "AB" : prettyNumber(r.mid1)}</td>
                <td className={r.mid2 === 0 ? "absent" : ""}>{r.mid2 === 0 ? "AB" : prettyNumber(r.mid2)}</td>
                <td className={r.internal === 0 ? "absent" : ""}>{r.internal === 0 ? "AB" : prettyNumber(r.internal)}</td>
                <td className={r.end_sem === 0 ? "absent" : ""}>{r.end_sem === 0 ? "AB" : prettyNumber(r.end_sem)}</td>
                <td>{subjScore === null ? "-" : prettyNumber(subjScore)}</td>
                <td>{grade}</td>
                <td>{result}</td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={6} style={{ textAlign: "right", fontWeight: 700 }}>Overall Score:</td>
            <td colSpan={3} style={{ fontWeight: 700 }}>{selectedOverall === null || typeof selectedOverall === "undefined" ? "-" : prettyNumber(selectedOverall)}</td>
          </tr>
        </tfoot>
      </table>
    );
  }

  // Feedback coloring
  function feedbackColor(feedbackText) {
    if (!feedbackText) return "neutral";
    // crude heuristics
    const ft = feedbackText.toLowerCase();
    if (ft.includes("strong") || ft.includes("keep it up") || ft.includes("good")) return "positive";
    if (ft.includes("needs") || ft.includes("attention") || ft.includes("average")) return "warning";
    if (ft.includes("critical") || ft.includes("low") || ft.includes("immediate")) return "critical";
    return "neutral";
  }

  // handle Enter key in pin input
  function onKeyPress(e) {
    if (e.key === "Enter") {
      doSearch(pin);
    }
  }

  return (
    <div className="rs-page">
      <header className="rs-topbar">
        <div className="rs-top-left">
          👋 Welcome, {loggedUser?.username || "Faculty"}
        </div>
        <div className="rs-top-right">
          <span className="rs-email">{/* optionally show user email */}</span>
          <a className="btn-logout" href="/logout">Logout</a>
        </div>
      </header>



      <main className="rs-container">
        <section className="rs-search">
          <div className="rs-search-left">
            <input
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              onKeyDown={onKeyPress}
              className="rs-input"
              placeholder="Enter PIN (e.g. 23189-CS-001)"
            />
            <button onClick={() => doSearch(pin)} className="rs-btn">Search</button>

            <div className="rs-recent">
              <div className="rs-recent-title">Recent</div>
              {recent.length === 0 && <div className="rs-recent-empty">No recent searches</div>}
              <ul>
                {recent.map((rpin) => (
                  <li key={rpin}><button onClick={() => onRecentClick(rpin)} className="link-like">{rpin}</button></li>
                ))}
              </ul>
            </div>
          </div>

          <div className="rs-search-right">
            {loading && <div className="rs-loading">Loading...</div>}
            {error && <div className="rs-error">{error}</div>}
            {student && (
              <div className="rs-student-summary">
                <div><strong>{student.name}</strong></div>
                <div>PIN: {student.pin}</div>
                <div>Branch: {student.branch} | Year: {student.exam_year || "-"}</div>
              </div>
            )}
          </div>
        </section>

        <section className="rs-main">
          <aside className="rs-semesters">
            <h4>Semesters</h4>
            {Array.from({ length: 6 }).map((_, i) => {
              const semNo = i + 1;
              const info = semInfo[semNo] || { hasData: false };
              return (
                <button
                  key={semNo}
                  className={`rs-sem-btn ${selectedSem === semNo ? "active" : ""} ${info.hasData ? "has-data" : "no-data"}`}
                  onClick={() => setSelectedSem(semNo)}
                >
                  Sem {semNo} {info.hasData ? <span className="dot" /> : null}
                </button>
              );
            })}
          </aside>

          <section className="rs-results">
            <div className="rs-results-header">
              <h3>Semester {selectedSem || "-"}</h3>
              <div className="rs-actions">
                
                <label className="rs-toggle">
                  <input type="checkbox" checked={showClassAvg} onChange={toggleClassAvg} />
                  Show Class Avg (dashed)
                </label>
              </div>
            </div>

            <div className="rs-results-table">
              {renderSubjectsTable()}
            </div>

            <div className={`rs-feedback ${feedbackColor(student?.feedback || (selectedSemData && selectedSemData.feedback) || "")}`}>
              <h4>Feedback</h4>
              <div className="rs-feedback-text">
                {selectedSemData && selectedSemData.feedback
                  ? selectedSemData.feedback
                  : (student && student.feedback) || "No feedback available for this semester."}
              </div>
            </div>

            <div className="rs-graph">
              <h4>Performance Trend</h4>
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="semester" />
                  <YAxis domain={[0, 100]} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="student" name="Student" stroke="#1976d2" strokeWidth={2} connectNulls />
                  {showClassAvg && <Line type="monotone" dataKey="classAvg" name="Class Avg" stroke="#ff9800" strokeWidth={2} strokeDasharray="5 5" connectNulls />}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>
        </section>
      </main>
    </div>
  );
}
