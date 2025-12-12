// src/components/GraphAnalysis.jsx
import React, { useEffect, useState, useRef } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";

const BRANCH_OPTIONS = ["CS", "EC", "ME", "EE", "IT"];

const YEAR_OPTIONS = [
  { value: 2022, label: "1st Year " },
  { value: 2023, label: "2nd Year " },
  { value: 2024, label: "3rd Year " },
];

const SEMESTER_MAP = {
  2022: [1, 2],
  2023: [3, 4],
  2024: [5, 6],
};
const GRAPH_FILTERS_KEY = "sppfs_graph_filters";

const PALETTE = [
  "#34D399",
  "#60A5FA",
  "#F59E0B",
  "#FB7185",
  "#A78BFA",
  "#F97316",
  "#10B981",
  "#3B82F6",
  "#EF4444",
  "#6366F1",
];

// Custom tick for X axis: split long subject names into two lines
const CustomXAxisTick = (props) => {
  const { x, y, payload } = props;

  // Split label into words and divide into two lines
  const words = String(payload.value || "").split(" ");
  const mid = Math.ceil(words.length / 2);
  const line1 = words.slice(0, mid).join(" ");
  const line2 = words.slice(mid).join(" ");



  return (
    <g transform={`translate(${x},${y})`}>
      <text
        dy={25}
        textAnchor="middle"
        fontSize={11}
        fill="#374151" // slate-700
      >
        <tspan x={0} dy="0">
          {line1}
        </tspan>
        {line2 && (
          <tspan x={0} dy="14">
            {line2}
          </tspan>
        )}
      </text>
    </g>
  );
};


function getPerformanceTag(avg) {
  const score = Number(avg ?? 0);
  if (score >= 75) {
    return {
      label: "Strong",
      className: "bg-emerald-50 text-emerald-700 border border-emerald-200",
    };
  }
  if (score >= 50) {
    return {
      label: "Average",
      className: "bg-amber-50 text-amber-700 border border-amber-200",
    };
  }
  return {
    label: "Weak",
    className: "bg-red-50 text-red-700 border border-red-200",
  };
}

export default function GraphAnalysis({ branch, year, semester, facultyName }) {
  const initialBatch = (() => {
    // 1. If props are passed, they win
    if (branch && year && semester) {
      return { branch, year, semester };
    }

    if (typeof window !== "undefined") {
      // 2. Try to use last saved filters from localStorage
      try {
        const saved = window.localStorage.getItem(GRAPH_FILTERS_KEY);
        if (saved) {
          const parsed = JSON.parse(saved);
          if (parsed.branch && parsed.year && parsed.semester) {
            return {
              branch: parsed.branch,
              year: Number(parsed.year),
              semester: Number(parsed.semester),
            };
          }
        }
      } catch (e) {
        console.warn("Failed to read saved graph filters:", e);
      }

      // 3. Fallback to SELECTED_BATCH if present
      if (window.SELECTED_BATCH) {
        return window.SELECTED_BATCH;
      }
    }

    // 4. Final hard-coded default
    return { branch: "CS", year: 2023, semester: 4 };
  })();


  const [selectedBranch, setSelectedBranch] = useState(initialBatch.branch);
  const [selectedYear, setSelectedYear] = useState(Number(initialBatch.year));
  const [selectedSemester, setSelectedSemester] = useState(
    Number(initialBatch.semester)
  );

    // Persist current filters so they survive refresh / next visit
  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(
        GRAPH_FILTERS_KEY,
        JSON.stringify({
          branch: selectedBranch,
          year: selectedYear,
          semester: selectedSemester,
        })
      );
    }
  }, [selectedBranch, selectedYear, selectedSemester]);


  const batch = {
    branch: selectedBranch,
    year: selectedYear,
    semester: selectedSemester,
  };

  const teacher =
    facultyName ||
    (typeof window !== "undefined" && window.FACULTY_NAME) ||
    "Faculty";

  const [subjectCards, setSubjectCards] = useState([]);
  const [barChartData, setBarChartData] = useState({ labels: [], values: [] });
  const [riskData, setRiskData] = useState({
    labels: [],
    values: [],
    counts: {},
  });
  const [summary, setSummary] = useState({
    classAverage: null,
    totalStudents: null,
    highRisk: null,
    passRate: null,
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const containerRef = useRef(null);

  useEffect(() => {
    if (!batch || !batch.branch || !batch.year || !batch.semester) {
      setError("No batch selected. Choose branch/year/semester.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    const subjUrl = `/api/results/graphs/subject_averages?branch=${encodeURIComponent(
      batch.branch
    )}&year=${batch.year}&semester=${batch.semester}`;
    const riskUrl = `/api/results/graphs/risk_distribution?branch=${encodeURIComponent(
      batch.branch
    )}&year=${batch.year}&semester=${batch.semester}`;

    (async () => {
      try {
        const [sRes, rRes] = await Promise.all([fetch(subjUrl), fetch(riskUrl)]);
        if (!sRes.ok)
          throw new Error(`subject_averages: ${sRes.status} ${sRes.statusText}`);
        if (!rRes.ok)
          throw new Error(`risk_distribution: ${rRes.status} ${rRes.statusText}`);

        const sJson = await sRes.json();
        const rJson = await rRes.json();

        let cards = [];
        if (Array.isArray(sJson.cards)) {
          cards = sJson.cards.map((c) => ({
            sub_code: c.sub_code || c.code,
            sub_name: c.sub_name || c.name,
            average: Number(c.average ?? c.avg ?? 0),
            pass_rate:
              c.pass_rate ??
              (c.pass ? Number(String(c.pass).replace("%", "")) : null),
            count: c.count ?? c.students ?? 0,
          }));
        } else if (Array.isArray(sJson.items)) {
          cards = sJson.items.map((c) => ({
            sub_code: c.sub_code || c.code,
            sub_name: c.sub_name || c.name,
            average: Number(c.average ?? c.avg ?? 0),
            pass_rate:
              c.pass_rate ??
              (c.pass ? Number(String(c.pass).replace("%", "")) : null),
            count: c.count ?? c.students ?? 0,
          }));
        } else if (Array.isArray(sJson.subjects)) {
          cards = sJson.subjects.map((c) => ({
            sub_code: c.sub_code || c.code,
            sub_name: c.sub_name || c.name,
            average: Number(c.average ?? c.avg ?? 0),
            pass_rate:
              c.pass_rate ??
              (c.pass ? Number(String(c.pass).replace("%", "")) : null),
            count: c.count ?? c.students ?? 0,
          }));
        } else {
          cards = [];
        }

        cards.sort((a, b) => (b.average || 0) - (a.average || 0));

        const labels = cards.map((c) => `${c.sub_name} (${c.sub_code})`);
        const values = cards.map((c) => c.average);

        setSubjectCards(cards);
        setBarChartData({ labels, values });

        const counts = rJson.counts || rJson.count || {};
        const labelsRisk =
          rJson.labels && Array.isArray(rJson.labels)
            ? rJson.labels
            : Object.keys(counts).length
            ? Object.keys(counts)
            : ["low", "medium", "high", "unknown"];

        const valuesRisk = labelsRisk.map(
          (k) => counts[k.toLowerCase()] ?? counts[k] ?? 0
        );

        setRiskData({
          labels: labelsRisk,
          values: valuesRisk,
          counts,
        });

        let classAverage = null;
        if (cards.length) {
          const sumAvg = cards.reduce(
            (sum, c) => sum + (Number(c.average) || 0),
            0
          );
          classAverage = Number((sumAvg / cards.length).toFixed(2));
        }

        const low = counts.low ?? counts.LOW ?? 0;
        const medium = counts.medium ?? counts.MEDIUM ?? 0;
        const high = counts.high ?? counts.HIGH ?? 0;
        const unknown = counts.unknown ?? counts.UNKNOWN ?? 0;

        const totalFromCounts = low + medium + high + unknown;
        const totalStudents = rJson.total_students ?? totalFromCounts ?? null;

        const passCount = low + medium;
        const passRate =
          totalStudents && totalStudents > 0
            ? Number(((passCount / totalStudents) * 100).toFixed(2))
            : null;

        setSummary({
          classAverage,
          totalStudents,
          highRisk: high,
          passRate,
        });

        setLoading(false);
      } catch (err) {
        console.error(err);
        setError(String(err.message || err));
        setLoading(false);
      }
    })();
  }, [selectedBranch, selectedYear, selectedSemester]);

  async function downloadPageAsPDF() {
    try {
      const node = containerRef.current;
      if (!node) throw new Error("Graph container not available");

      await new Promise((r) => setTimeout(r, 250));

      const [{ default: html2canvas }, { default: jsPDF }] = await Promise.all(
        [import("html2canvas"), import("jspdf")]
      );

      const canvas = await html2canvas(node, {
        scale: 2,
        useCORS: true,
        allowTaint: true,
      });
      const imgData = canvas.toDataURL("image/png");

      const pdf = new jsPDF({
        orientation: "portrait",
        unit: "pt",
        format: "a4",
      });
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();

      const ratio = canvas.width / pageWidth;
      const totalPages = Math.ceil(canvas.height / (pageHeight * ratio));

      if (totalPages === 1) {
        pdf.addImage(imgData, "PNG", 0, 0, pageWidth, canvas.height / ratio);
      } else {
        let y = 0;
        for (let i = 0; i < totalPages; i++) {
          const segHeight = Math.min(
            canvas.height - y,
            Math.floor(pageHeight * ratio)
          );

          const tmpCanvas = document.createElement("canvas");
          tmpCanvas.width = canvas.width;
          tmpCanvas.height = segHeight;
          const tctx = tmpCanvas.getContext("2d");
          tctx.drawImage(
            canvas,
            0,
            y,
            canvas.width,
            segHeight,
            0,
            0,
            canvas.width,
            segHeight
          );
          const segData = tmpCanvas.toDataURL("image/png");

          const segPdfHeight = segHeight / ratio;
          pdf.addImage(segData, "PNG", 0, 0, pageWidth, segPdfHeight);

          if (i < totalPages - 1) pdf.addPage();
          y += segHeight;
        }
      }

      pdf.save(
        `graph-analysis-${batch.branch}-${batch.year}-sem${batch.semester}.pdf`
      );
    } catch (err) {
      console.warn("PDF export fallback (print) because PDF generation failed:", err);
      window.print();
    }
  }

  const { classAverage, totalStudents, highRisk, passRate } = summary;
  const half = Math.ceil(subjectCards.length / 2);
  const leftSubjects = subjectCards.slice(0, half);
  const rightSubjects = subjectCards.slice(half);

  const handleLogout = () => {
    window.location.href = "/logout";
  };

  
  return (
    <div
      ref={containerRef}
      className="space-y-6 pb-10"
      style={{
        width: "80%",
        margin: "0 auto",
      }}
    >
      {/* TOP WELCOME + EXPORT */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">
            Welcome back, <span className="text-blue-700">{teacher}</span>
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Class performance overview and risk insights for the selected batch.
          </p>
        </div>
        <button
          onClick={downloadPageAsPDF}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
        >
          📥 Export as PDF
        </button>
      </div>

      {/* FILTERS CARD */}
      <div className="card border border-slate-200 rounded-2xl shadow-sm bg-white">
        <div className="px-4 pt-4 pb-3">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-base font-semibold text-slate-800">Graph Analysis</span>
            <span className="text-xs text-slate-400">Configure branch and semester to view analytics.</span>
          </div>

          <div className="flex flex-wrap gap-4 text-sm">
            {/* Branch */}
            <label className="flex flex-col min-w-[140px]">
              <span className="text-xs font-medium text-slate-600 mb-1">Branch </span>
              <select
                className="mt-0 block w-full text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                style={{
                  borderRadius: "9999px",
                  border: "1px solid #d1d5db",
                  background: "#f9fafb",
                  padding: "0.5rem 0.9rem",
                  boxShadow: "0 1px 2px rgba(15,23,42,0.05)",
                }}
                value={selectedBranch}
                onChange={(e) => setSelectedBranch(e.target.value)}
              >
                {BRANCH_OPTIONS.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </label>

            {/* Exam Year */}
            <label className="flex flex-col min-w-[170px]">
              <span className="text-xs font-medium text-slate-600 mb-1"> Exam Year </span>
              <select
                className="mt-0 block w-full text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                style={{
                  borderRadius: "9999px",
                  border: "1px solid #d1d5db",
                  background: "#f9fafb",
                  padding: "0.5rem 0.9rem",
                  boxShadow: "0 1px 2px rgba(15,23,42,0.05)",
                }}
                value={selectedYear}
                onChange={(e) => {
                  const y = Number(e.target.value);
                  setSelectedYear(y);
                  const sems = SEMESTER_MAP[y] || [];
                  if (sems.length > 0) {
                    setSelectedSemester(sems[0]);
                  }
                }}
              >
                {YEAR_OPTIONS.map((y) => (
                  <option key={y.value} value={y.value}>
                    {y.label}
                  </option>
                ))}
              </select>
            </label>

            {/* Semester */}
            <label className="flex flex-col min-w-[140px]">
              <span className="text-xs font-medium text-slate-600 mb-1"> Semester </span>
              <select
                className="mt-0 block w-full text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                style={{
                  borderRadius: "9999px",
                  border: "1px solid #d1d5db",
                  background: "#f9fafb",
                  padding: "0.5rem 0.9rem",
                  boxShadow: "0 1px 2px rgba(15,23,42,0.05)",
                }}
                value={selectedSemester}
                onChange={(e) => setSelectedSemester(Number(e.target.value))}
              >
                {(SEMESTER_MAP[selectedYear] || []).map((s) => (
                  <option key={s} value={s}>
                    {`Sem ${s}`}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
      </div>

      {/* KPI SUMMARY */}
      {!loading && !error && (
        <div
          className="mt-8 w-full"
          style={{
            display: "flex",
            gap: "24px",
            flexWrap: "nowrap",
          }}
        >
          {/* Class Average */}
          <div style={{ flex: "1 1 0", background: "#f9fafb", borderRadius: "20px", border: "1px solid #e5e7eb", padding: "24px" }}>
            <div style={{ fontSize: "14px", fontWeight: 600, color: "#4b5563" }}>Class Average</div>
            <div style={{ marginTop: "12px", fontSize: "28px", fontWeight: 600, color: "#111827" }}>
              {classAverage != null ? `${classAverage}%` : "—"}
            </div>
          </div>

          {/* Total Students */}
          <div style={{ flex: "1 1 0", background: "#f9fafb", borderRadius: "20px", border: "1px solid #e5e7eb", padding: "24px" }}>
            <div style={{ fontSize: "14px", fontWeight: 600, color: "#4b5563" }}>Total Students</div>
            <div style={{ marginTop: "12px", fontSize: "28px", fontWeight: 600, color: "#111827" }}>
              {totalStudents != null ? totalStudents : "—"}
            </div>
          </div>

          {/* High Risk Students */}
          <div style={{ flex: "1 1 0", background: "#f9fafb", borderRadius: "20px", border: "1px solid #e5e7eb", padding: "24px" }}>
            <div style={{ fontSize: "14px", fontWeight: 600, color: "#4b5563" }}>High Risk Students</div>
            <div style={{ marginTop: "12px", fontSize: "28px", fontWeight: 600, color: "#b91c1c" }}>
              {highRisk != null ? highRisk : 0}
            </div>
          </div>

          {/* Pass Rate (est.) */}
          <div style={{ flex: "1 1 0", background: "#f9fafb", borderRadius: "20px", border: "1px solid #e5e7eb", padding: "24px" }}>
            <div style={{ fontSize: "14px", fontWeight: 600, color: "#4b5563" }}>Pass Rate (est.)</div>
            <div style={{ marginTop: "12px", fontSize: "28px", fontWeight: 600, color: "#059669" }}>
              {passRate != null ? `${passRate}%` : "—"}
            </div>
          </div>
        </div>
      )}

      {loading && <div className="py-10 text-center text-slate-600">Loading graphs…</div>}
      {error && (
        <div className="py-6 px-4 bg-red-50 border border-red-100 text-red-700 rounded-lg">Error: {error}</div>
      )}

      {/* MAIN ANALYTICS CARD */}
      {!loading && !error && (
        <div className="card border border-slate-200 rounded-2xl shadow-sm bg-white p-5 space-y-8">
          {/* Subject-wise Performance */}
          <section>
            <h2 className="text-md font-semibold mb-2 text-slate-900">Subject-wise Performance</h2>
            <p className="text-sm text-slate-500 mb-4">Quick snapshot of each subject's overall performance.</p>

                <div className="space-y-4">
                  {subjectCards.length === 0 ? (
                    <div className="text-slate-500">
                      No subject data available for this batch.
                    </div>
                  ) : (
                    <div
                      style={{
                        display: "flex",
                        gap: "24px",
                        alignItems: "flex-start",
                        width: "100%",
                      }}
                    >
                      {/* LEFT COLUMN (first half) */}
                      <div
                        style={{
                          flex: 1,
                          paddingRight: "12px",
                          borderRight: "1px solid rgba(148,163,184,0.35)", // subtle divider line
                        }}
                      >
                        {leftSubjects.map((c, idx) => {
                          const perf = getPerformanceTag(c.average);
                          const paletteIndex = idx;

                          return (
                            <div
                              key={c.sub_code}
                              className="flex items-center gap-4 bg-slate-50/70 rounded-xl px-3 py-3 mb-4"
                            >
                              {/* Rank badge */}
                              <div className="w-10 flex justify-center">
                                <div className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-slate-100 text-xs font-semibold text-slate-700">
                                  #{idx + 1}
                                </div>
                              </div>

                              {/* Subject info */}
                              <div style={{ minWidth: 220 }}>
                                <div className="text-sm text-slate-500">{c.sub_name}</div>
                                <div className="text-base font-semibold text-slate-900">
                                  {c.sub_code}
                                </div>
                              </div>

                              {/* Progress bar */}
                              <div style={{ flex: 1 }}>
                                <div className="progress-track">
                                  <div
                                    className="progress-fill"
                                    style={{
                                      width: `${Math.max(
                                        0,
                                        Math.min(100, c.average || 0)
                                      )}%`,
                                      background: PALETTE[paletteIndex % PALETTE.length],
                                    }}
                                  />
                                </div>
                                <div className="flex justify-between text-xs text-slate-500 mt-2">
                                  <span>Students: {c.count || 0}</span>
                                  <span>Avg: {(c.average ?? 0).toFixed(2)}%</span>
                                </div>
                              </div>

                              {/* Stats & tag */}
                              <div
                                style={{ width: 160, textAlign: "right" }}
                                className="space-y-1"
                              >
                                <div className="text-xs text-slate-500">
                                  Pass: {c.pass_rate != null ? `${c.pass_rate}%` : "N/A"}
                                </div>
                                <div
                                  className={
                                    "inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium " +
                                    perf.className
                                  }
                                >
                                  {perf.label}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>

                      {/* RIGHT COLUMN (second half) */}
                      <div
                        style={{
                          flex: 1,
                          paddingLeft: "12px",
                        }}
                      >
                        {rightSubjects.map((c, idx) => {
                          const perf = getPerformanceTag(c.average);
                          const rank = leftSubjects.length + idx + 1;
                          const paletteIndex = leftSubjects.length + idx;

                          return (
                            <div
                              key={c.sub_code}
                              className="flex items-center gap-4 bg-slate-50/70 rounded-xl px-3 py-3 mb-4"
                            >
                              {/* Rank badge */}
                              <div className="w-10 flex justify-center">
                                <div className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-slate-100 text-xs font-semibold text-slate-700">
                                  #{rank}
                                </div>
                              </div>

                              {/* Subject info */}
                              <div style={{ minWidth: 220 }}>
                                <div className="text-sm text-slate-500">{c.sub_name}</div>
                                <div className="text-base font-semibold text-slate-900">
                                  {c.sub_code}
                                </div>
                              </div>

                              {/* Progress bar */}
                              <div style={{ flex: 1 }}>
                                <div className="progress-track">
                                  <div
                                    className="progress-fill"
                                    style={{
                                      width: `${Math.max(
                                        0,
                                        Math.min(100, c.average || 0)
                                      )}%`,
                                      background: PALETTE[paletteIndex % PALETTE.length],
                                    }}
                                  />
                                </div>
                                <div className="flex justify-between text-xs text-slate-500 mt-2">
                                  <span>Students: {c.count || 0}</span>
                                  <span>Avg: {(c.average ?? 0).toFixed(2)}%</span>
                                </div>
                              </div>

                              {/* Stats & tag */}
                              <div
                                style={{ width: 160, textAlign: "right" }}
                                className="space-y-1"
                              >
                                <div className="text-xs text-slate-500">
                                  Pass: {c.pass_rate != null ? `${c.pass_rate}%` : "N/A"}
                                </div>
                                <div
                                  className={
                                    "inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium " +
                                    perf.className
                                  }
                                >
                                  {perf.label}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>

          </section>

          {/* Bar chart */}
          <section>
            <h3 className="text-md font-semibold mb-2 text-slate-900">Subject Average Comparison</h3>
            <p className="text-sm text-slate-500 mb-4">Visual comparison of subject-wise averages for the selected batch.</p>

            <div className="card border border-slate-100 rounded-xl p-3 bg-slate-50/70">
              {barChartData.values.length === 0 ? (
                <div className="text-slate-500">No data available to render bar chart.</div>
              ) : (
                    <div style={{ width: "100%", height: 380 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={barChartData.labels.map((label, i) => ({
                            name: label,
                            value: barChartData.values[i],
                          }))}
                          // less bottom margin so the plot area is taller
                          margin={{ top: 20, right: 20, left: 10, bottom: 90 }}
                        >

                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis
                          dataKey="name"
                          interval={0}
                          height={70}
                          tickMargin={10}    
                          tick={<CustomXAxisTick />}       // ← uses the custom 2-line labels
                        />
                        <YAxis domain={[0, 100]} />
                        <Tooltip />
                        <Bar dataKey="value" fill="#3b82f6" />
                      </BarChart>
                    </ResponsiveContainer>

                </div>
              )}
            </div>
          </section>

          {/* Pie chart */}
          <section>
            <h3 className="text-md font-semibold mb-2 text-slate-900">Risk Distribution</h3>
            <p className="text-sm text-slate-500 mb-4">Distribution of students by risk category (High / Medium / Low / Unknown).</p>

            <div className="card flex flex-col items-center justify-center border border-slate-100 rounded-xl p-4 bg-slate-50/70">
              {riskData.values.length === 0 ? (
                <div className="text-slate-500">No risk distribution data available.</div>
              ) : (
                <>
                  <div style={{ width: 380, height: 300 }}>
                    <ResponsiveContainer>
                      <PieChart>
                        <Pie
                          data={riskData.labels.map((label, i) => ({ name: label, value: riskData.values[i] || 0 }))}
                          dataKey="value"
                          nameKey="name"
                          outerRadius={100}
                          label
                        >
                          {riskData.values.map((_, i) => (
                            <Cell key={`cell-${i}`} fill={PALETTE[i % PALETTE.length]} />
                          ))}
                        </Pie>
                        <Legend layout="horizontal" verticalAlign="bottom" />
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>

                  <div className="mt-4 text-sm text-slate-600 text-center">
                    {totalStudents != null && (
                      <div>
                        <span className="font-semibold">{highRisk ?? 0}</span>{" "}
                        students (
                        {totalStudents ? (((highRisk ?? 0) / totalStudents) * 100).toFixed(1) : "0.0"}
                        %) are in <span className="text-red-600 font-semibold">high risk</span>.
                      </div>
                    )}
                    {passRate != null && (
                      <div className="mt-1">
                        Overall estimated pass rate: <span className="font-semibold">{passRate}%</span>.
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
