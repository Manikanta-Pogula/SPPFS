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

const PALETTE = [
  "#34D399", "#60A5FA", "#F59E0B", "#FB7185", "#A78BFA",
  "#F97316", "#10B981", "#3B82F6", "#EF4444", "#6366F1",
];

export default function GraphAnalysis({ branch, year, semester, facultyName }) {
  // resolve batch: props first, then window.SELECTED_BATCH if provided by server template
  const batch = (() => {
    if (branch && year && semester) return { branch, year, semester };
    if (typeof window !== "undefined" && window.SELECTED_BATCH) return window.SELECTED_BATCH;
    return null;
  })();

  const teacher = facultyName || (typeof window !== "undefined" && window.FACULTY_NAME) || "Faculty";

  const [subjectCards, setSubjectCards] = useState([]);
  const [barChartData, setBarChartData] = useState({ labels: [], values: [] });
  const [riskData, setRiskData] = useState({ labels: [], values: [], counts: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const containerRef = useRef(null);

  useEffect(() => {
    if (!batch) {
      setError("No batch selected. Provide branch/year/semester via props or window.SELECTED_BATCH.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    const subjUrl = `/api/results/graphs/subject_averages?branch=${encodeURIComponent(batch.branch)}&year=${batch.year}&semester=${batch.semester}`;
    const riskUrl = `/api/results/graphs/risk_distribution?branch=${encodeURIComponent(batch.branch)}&year=${batch.year}&semester=${batch.semester}`;

    (async () => {
      try {
        const [sRes, rRes] = await Promise.all([fetch(subjUrl), fetch(riskUrl)]);
        if (!sRes.ok) throw new Error(`subject_averages: ${sRes.status} ${sRes.statusText}`);
        if (!rRes.ok) throw new Error(`risk_distribution: ${rRes.status} ${rRes.statusText}`);

        const sJson = await sRes.json();
        const rJson = await rRes.json();

        // NORMALIZE SUBJECT DATA (support several backend shapes you've used)
        let cards = [];
        if (Array.isArray(sJson.cards)) {
          cards = sJson.cards.map(c => ({
            sub_code: c.sub_code || c.code,
            sub_name: c.sub_name || c.sub_name || c.name,
            average: Number(c.average ?? c.avg ?? 0),
            pass_rate: c.pass_rate ?? (c.pass ? Number(String(c.pass).replace("%", "")) : null),
            count: c.count ?? c.students ?? 0,
          }));
        } else if (Array.isArray(sJson.items)) {
          cards = sJson.items.map(c => ({
            sub_code: c.sub_code || c.code,
            sub_name: c.sub_name || c.name,
            average: Number(c.average ?? c.avg ?? 0),
            pass_rate: c.pass_rate ?? (c.pass ? Number(String(c.pass).replace("%", "")) : null),
            count: c.count ?? c.students ?? 0,
          }));
        } else if (Array.isArray(sJson.subjects)) {
          cards = sJson.subjects.map(c => ({
            sub_code: c.sub_code || c.code,
            sub_name: c.sub_name || c.name,
            average: Number(c.average ?? c.avg ?? 0),
            pass_rate: c.pass_rate ?? (c.pass ? Number(String(c.pass).replace("%", "")) : null),
            count: c.count ?? c.students ?? 0,
          }));
        } else {
          // fallback: empty
          cards = [];
        }

        // keep display order stable: sort by average desc (like screenshot)
        cards.sort((a, b) => (b.average || 0) - (a.average || 0));

        const labels = cards.map(c => `${c.sub_name} (${c.sub_code})`);
        const values = cards.map(c => c.average);

        setSubjectCards(cards);
        setBarChartData({ labels, values });

        // normalize risk payload
        const counts = rJson.counts || rJson.count || rJson.counts || {};
        const labelsRisk = Object.keys(counts).length ? Object.keys(counts) : (rJson.labels || ["low","medium","high","unknown"]);
        const valuesRisk = labelsRisk.map(k => counts[k] ?? 0);
        setRiskData({ labels: labelsRisk, values: valuesRisk, counts });

        setLoading(false);
      } catch (err) {
        console.error(err);
        setError(String(err.message || err));
        setLoading(false);
      }
    })();
  }, [branch, year, semester]);

  // multi-page PDF function: splits a long canvas to multiple pages.
  async function downloadPageAsPDF() {
    try {
      const node = containerRef.current;
      if (!node) throw new Error("Graph container not available");

      // ensure rendering / layout done (micro-wait)
      await new Promise(r => setTimeout(r, 250));

      const [{ default: html2canvas }, { default: jsPDF }] = await Promise.all([
        import("html2canvas"),
        import("jspdf"),
      ]);

      const canvas = await html2canvas(node, { scale: 2, useCORS: true, allowTaint: true });
      const imgData = canvas.toDataURL("image/png");

      // create a PDF in 'pt' units (A4)
      const pdf = new jsPDF({ orientation: "portrait", unit: "pt", format: "a4" });
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();

      // compute ratio between canvas px and pdf points
      const ratio = canvas.width / pageWidth;
      const totalPages = Math.ceil(canvas.height / (pageHeight * ratio));

      if (totalPages === 1) {
        pdf.addImage(imgData, "PNG", 0, 0, pageWidth, canvas.height / ratio);
      } else {
        // slice canvas per page
        let y = 0;
        for (let i = 0; i < totalPages; i++) {
          const segHeight = Math.min(canvas.height - y, Math.floor(pageHeight * ratio));

          // create temp canvas for slice
          const tmpCanvas = document.createElement("canvas");
          tmpCanvas.width = canvas.width;
          tmpCanvas.height = segHeight;
          const tctx = tmpCanvas.getContext("2d");
          tctx.drawImage(canvas, 0, y, canvas.width, segHeight, 0, 0, canvas.width, segHeight);
          const segData = tmpCanvas.toDataURL("image/png");

          const segPdfHeight = segHeight / ratio;
          pdf.addImage(segData, "PNG", 0, 0, pageWidth, segPdfHeight);

          if (i < totalPages - 1) pdf.addPage();
          y += segHeight;
        }
      }

      pdf.save(`graph-analysis-${batch.branch}-${batch.year}-sem${batch.semester}.pdf`);
    } catch (err) {
      console.warn("PDF export fallback (print) because PDF generation failed:", err);
      window.print();
    }
  }

  return (
    <div className="card" ref={containerRef}>
      <div className="flex justify-between items-start mb-6">
        <div>
          <h1 className="text-lg font-semibold">Graph Analysis</h1>
          <div className="text-sm text-slate-600">
            Auto-fetched batch: {batch ? `${batch.branch} — ${batch.year} — Sem ${batch.semester}` : "(no batch)"}
          </div>
        </div>

        <div className="text-right">
          <div className="text-sm text-slate-600">Welcome back, <strong>{teacher}</strong></div>
          <button onClick={downloadPageAsPDF} className="mt-2 inline-flex items-center gap-2 px-3 py-1 bg-blue-600 text-white rounded text-sm">
            📥 Export as PDF
          </button>
        </div>
      </div>

      {loading && <div className="py-10 text-center text-slate-600">Loading graphs…</div>}
      {error && <div className="py-6 px-4 bg-red-50 border border-red-100 text-red-700 rounded">Error: {error}</div>}

      {!loading && !error && (
        <div className="space-y-8">
          {/* subject cards - vertical list to match screenshot */}
          <section>
            <h2 className="text-md font-semibold mb-2">Subject-wise Performance</h2>
            <p className="text-sm text-slate-500 mb-4">Quick snapshot of each subject's overall performance.</p>

            <div className="space-y-4">
              {subjectCards.length === 0 && <div className="text-slate-500">No subject data available for this batch.</div>}
              {subjectCards.map((c, idx) => (
                <div key={c.sub_code} className="flex items-center gap-4">
                  <div style={{ minWidth: 220 }}>
                    <div className="text-sm text-slate-500">{c.sub_name}</div>
                    <div className="text-base font-bold">{c.sub_code}</div>
                  </div>

                  <div style={{ flex: 1 }}>
                    <div className="progress-track">
                      <div
                        className="progress-fill"
                        style={{
                          width: `${Math.max(0, Math.min(100, c.average || 0))}%`,
                          background: PALETTE[idx % PALETTE.length]
                        }}
                      />
                    </div>
                    <div className="text-center text-xs text-slate-500 mt-2">Students: {c.count || 0}</div>
                  </div>

                  <div style={{ width: 120, textAlign: "right" }}>
                    <div className="small-stat">{(c.average ?? 0).toFixed(2)}%</div>
                    <div className="text-xs text-slate-500 mt-1">Pass: {c.pass_rate != null ? `${c.pass_rate}%` : "N/A"}</div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Bar chart */}
          <section>
            <h3 className="text-md font-semibold mb-2">Subject Average Comparison</h3>
            <p className="text-sm text-slate-500 mb-4">Visual comparison of subject-wise averages for the selected batch.</p>

            <div className="card">
              {barChartData.values.length === 0 ? (
                <div className="text-slate-500">No data available to render bar chart.</div>
              ) : (
                <div style={{ width: "100%", height: 320 }}>
                  <ResponsiveContainer>
                    <BarChart
                      data={barChartData.labels.map((label, i) => ({ name: label, value: barChartData.values[i] }))}
                      margin={{ top: 20, right: 20, left: 10, bottom: 80 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" angle={-45} textAnchor="end" interval={0} height={80} />
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
            <h3 className="text-md font-semibold mb-2">Risk Distribution</h3>
            <p className="text-sm text-slate-500 mb-4">Distribution of students by risk category (High / Medium / Low / Unknown).</p>

            <div className="card flex items-center justify-center">
              {riskData.values.length === 0 ? (
                <div className="text-slate-500">No risk distribution data available.</div>
              ) : (
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
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
