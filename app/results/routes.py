# app/results/routes.py
import re
from flask import Blueprint, request, jsonify, send_file
from io import StringIO
import csv
from collections import defaultdict
from typing import Optional, Tuple

from app import db
from app.models import Student, Mark, Subject
from app.utils import compute_subject_score, compute_overall_score, map_risk, generate_feedback

results_bp = Blueprint("results", __name__, url_prefix="/api/results")

# -------------------------
# Helpers
# -------------------------
PIN_REGEX = re.compile(r'^\s*\d{2,}-[A-Za-z0-9]+-\d+\s*$', re.IGNORECASE)


def _is_pin_valid(pin: str) -> bool:
    if not pin:
        return False
    p = str(pin).strip()
    if PIN_REGEX.match(p):
        return True
    if len(p) >= 7 and '-' in p and any(ch.isdigit() for ch in p):
        return True
    return False


def compute_grade_and_result(score: Optional[float]) -> Tuple[str, str]:
    """
    Compute grade (A+/A/B/C/D/F or N/A) and Pass/Fail string based on score (0-100).
    Pass threshold: score >= 40.
    If score is None -> grade "N/A", result "❌ Fail" (no data).
    """
    if score is None:
        return "N/A", "❌ Fail"

    if score >= 90:
        grade = "A+"
    elif score >= 80:
        grade = "A"
    elif score >= 70:
        grade = "B"
    elif score >= 60:
        grade = "C"
    elif score >= 50:
        grade = "D"
    else:
        grade = "F"

    result = "✅ Pass" if score >= 40 else "❌ Fail"
    return grade, result


def _compute_student_score_for_sem(student, semester):
    """
    Returns: (overall_score: Optional[float], subject_count: int, details: List[dict])
    Each detail contains per-subject raw components, computed subject_score, risk, attendance,
    and now also 'grade' and 'result'.
    """
    marks = Mark.query.filter_by(student_id=student.id, semester=semester).all()
    details, scores = [], []

    for m in marks:
        subj = Subject.query.filter_by(sub_code=m.sub_code).first()
        sub_name = subj.sub_name if subj else ""

        ss = m.subject_score
        if ss is None:
            try:
                comps = {
                    "attendance": m.attendance,
                    "mid1": m.mid1,
                    "mid2": m.mid2,
                    "internal": m.internal,
                    "end_sem": m.end_sem,
                }
                ss = compute_subject_score(comps)
            except Exception:
                ss = None

        if ss is not None:
            scores.append(ss)

        # compute grade and pass/fail based on computed subject_score (0-100)
        grade, result = compute_grade_and_result(ss)

        details.append({
            "sub_code": m.sub_code,
            "sub_name": sub_name,
            "mid1": m.mid1,
            "mid2": m.mid2,
            "internal": m.internal,
            "end_sem": m.end_sem,
            "total": m.total,
            "attendance": m.attendance,
            "subject_score": ss,
            "risk": m.risk,
            "grade": grade,
            "result": result
        })

    overall = compute_overall_score(scores) if scores else None
    return overall, len(details), details


# -------------------------
# 1) Search / listing
# -------------------------
@results_bp.route("/search")
def search_student():
    pin = (request.args.get("pin") or "").strip()
    q = (request.args.get("q") or "").strip()
    branch = (request.args.get("branch") or "").strip()
    exam_year = request.args.get("year")
    semester = request.args.get("semester")

    # single student
    if pin:
        student = Student.query.filter_by(pin=pin).first()
        if not student:
            return jsonify({"error": "Student not found"}), 404

        sem = int(semester) if semester and semester.isdigit() else None
        if sem is None:
            marks_by_sem = {}
            for m in Mark.query.filter_by(student_id=student.id).order_by(Mark.semester).all():
                key = str(m.semester)
                marks_by_sem.setdefault(key, []).append({
                    "sub_code": m.sub_code,
                    "mid1": m.mid1,
                    "mid2": m.mid2,
                    "internal": m.internal,
                    "end_sem": m.end_sem,
                    "total": m.total,
                    "attendance": m.attendance,
                    "subject_score": m.subject_score,
                    "risk": m.risk
                })
            return jsonify({
                "student": {
                    "pin": student.pin,
                    "name": student.name,
                    "branch": student.branch,
                    "exam_year": student.exam_year
                },
                "marks_by_semester": marks_by_sem
            })

        overall, count, details = _compute_student_score_for_sem(student, sem)

        risk_subjects = [d["sub_name"] for d in details if d.get("subject_score") and d["subject_score"] < 40]
        atts = [d.get("attendance") for d in details if d.get("attendance") is not None]
        avg_attendance = (sum(atts) / len(atts)) if atts else None

        feedback = generate_feedback(student.name, overall, risk_subjects, avg_attendance)

        return jsonify({
            "student": {
                "pin": student.pin,
                "name": student.name,
                "branch": student.branch,
                "exam_year": student.exam_year
            },
            "semester": sem,
            "overall_score": overall,
            "subject_count": count,
            "subjects": details,
            "attendance": avg_attendance,
            "feedback": feedback
        })

    # batch listing
    page = int(request.args.get("page") or 1)
    per_page = int(request.args.get("per_page") or 50)
    sort = (request.args.get("sort") or "pin").lower()
    order = (request.args.get("order") or "asc").lower()

    query = Student.query
    if branch:
        query = query.filter_by(branch=branch)
    if exam_year and exam_year.isdigit():
        query = query.filter_by(exam_year=int(exam_year))
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Student.pin.ilike(like), Student.name.ilike(like)))

    pagination = query.order_by(Student.pin).paginate(page=page, per_page=per_page, error_out=False)
    temp_rows, batch_scores = [], []
    sem = int(semester) if semester and semester.isdigit() else None

    for s in pagination.items:
        if not _is_pin_valid(s.pin):  # skip invalid
            continue
        if s.name and 'polytechnic' in s.name.lower():
            continue

        overall, subj_count, details = None, 0, []
        attendance_val = None
        if sem:
            overall, subj_count, details = _compute_student_score_for_sem(s, sem)
            atts = [d.get("attendance") for d in details if d.get("attendance") is not None]
            if atts:
                attendance_val = sum(atts) / len(atts)

        temp_rows.append({
            "pin": s.pin,
            "name": s.name,
            "branch": s.branch,
            "exam_year": s.exam_year,
            "attendance": attendance_val,
            "overall_score": overall,
            "subject_count": subj_count,
            "risk": map_risk(overall) if overall is not None else None
        })
        if overall is not None:
            batch_scores.append(overall)

    # sorting
    reverse = (order == "desc")
    if sort == "name":
        temp_rows.sort(key=lambda x: (x["name"] or "").lower(), reverse=reverse)
    elif sort == "risk":
        rank = {"high": 2, "medium": 1, "low": 0, None: -1}
        temp_rows.sort(key=lambda x: rank.get((x.get("risk") or "").lower(), -1), reverse=reverse)
    elif sort in ("class_avg", "overall"):
        temp_rows.sort(key=lambda x: (x.get("overall_score") is None, x.get("overall_score") or 0), reverse=reverse)
    elif sort == "attendance":
        temp_rows.sort(key=lambda x: (x.get("attendance") is None, x.get("attendance") or 0), reverse=reverse)
    else:
        temp_rows.sort(key=lambda x: x["pin"], reverse=reverse)

    class_avg = (sum(batch_scores) / len(batch_scores)) if batch_scores else None

    return jsonify({
        "total": len(temp_rows),
        "page": page,
        "per_page": per_page,
        "class_average": class_avg,
        "items": temp_rows
    })


# -------------------------
# 2) Batch overview
# -------------------------
@results_bp.route("/overview")
def batch_overview():
    branch = (request.args.get("branch") or "").strip()
    exam_year = request.args.get("year")
    semester = request.args.get("semester")

    if not branch or not exam_year or not semester:
        return jsonify({"error": "branch, year and semester required"}), 400

    year_i, sem_i = int(exam_year), int(semester)
    students = Student.query.filter_by(branch=branch, exam_year=year_i).all()

    risk_counts = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
    overall_vals, attendance_vals = [], []

    for s in students:
        if not _is_pin_valid(s.pin):
            continue
        overall, _, details = _compute_student_score_for_sem(s, sem_i)
        if overall is None:
            risk_counts["unknown"] += 1
        else:
            risk_counts[map_risk(overall) or "unknown"] += 1
            overall_vals.append(overall)
        atts = [d.get("attendance") for d in details if d.get("attendance") is not None]
        if atts:
            attendance_vals.append(sum(atts) / len(atts))

    return jsonify({
        "total_students": len(students),
        "risk_counts": risk_counts,
        "avg_attendance": (sum(attendance_vals) / len(attendance_vals)) if attendance_vals else None,
        "avg_class_performance": (sum(overall_vals) / len(overall_vals)) if overall_vals else None
    })


# -------------------------
# 3) Export CSV
# -------------------------
@results_bp.route("/export")
def export_csv():
    branch = (request.args.get("branch") or "").strip()
    exam_year = request.args.get("year")
    semester = request.args.get("semester")
    q = (request.args.get("q") or "").strip()

    query = Student.query
    if branch:
        query = query.filter_by(branch=branch)
    if exam_year and exam_year.isdigit():
        query = query.filter_by(exam_year=int(exam_year))
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Student.pin.ilike(like), Student.name.ilike(like)))

    students = query.order_by(Student.pin).all()
    sem_i = int(semester) if semester and semester.isdigit() else None

    out = StringIO()
    writer = csv.writer(out)
    writer.writerow(["PIN", "Name", "Branch", "ExamYear", "Attendance%", "OverallScore", "Risk"])

    for s in students:
        if not _is_pin_valid(s.pin):
            continue
        overall, overall_att = None, None
        if sem_i:
            overall, _, details = _compute_student_score_for_sem(s, sem_i)
            atts = [d.get("attendance") for d in details if d.get("attendance") is not None]
            if atts:
                overall_att = sum(atts) / len(atts)
        writer.writerow([s.pin, s.name, s.branch, s.exam_year, overall_att or "", overall or "", map_risk(overall) or ""])

    out.seek(0)
    return send_file(
        StringIO(out.getvalue()),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"students_export_{branch}_{exam_year}_{semester}.csv"
    )


# -------------------------
# Institution
# -------------------------
@results_bp.route("/institution")
def get_institution():
    from app.models import Institution
    inst = Institution.query.first()
    return jsonify({"name": inst.name if inst else ""})


# -------------------------
# Graph endpoints (updated)
# -------------------------
@results_bp.route("/graphs/subject_averages")
def subject_averages_graph():
    """
    Returns JSON with:
    - "cards": list of subject cards [{sub_code, sub_name, average, pass_rate, count}]
    - "chart": { "labels": [...subject names/codes...], "values": [...averages...] }
    Required query params: branch, year, semester
    """
    branch = (request.args.get("branch") or "").strip()
    year = request.args.get("year")
    semester = request.args.get("semester")

    if not branch or not year or not semester:
        return jsonify({"error": "branch, year, semester required"}), 400

    year_i, sem_i = int(year), int(semester)
    # fetch students for batch
    students = Student.query.filter_by(branch=branch, exam_year=year_i).all()

    # accumulate per-subject sums and pass counts
    subject_sum = {}     # sub_code -> sum of subject_score (percent)
    subject_count = {}   # sub_code -> number of students with score
    subject_pass = {}    # sub_code -> number of students passing (subject_score >= 40)
    subject_name_map = {}  # sub_code -> sub_name (from Subject table)

    for s in students:
        marks = Mark.query.filter_by(student_id=s.id, semester=sem_i).all()
        for m in marks:
            sub_code = m.sub_code
            # get or compute subject-level percent score (0-100)
            score = m.subject_score
            if score is None:
                try:
                    comps = {
                        "attendance": m.attendance,
                        "mid1": m.mid1,
                        "mid2": m.mid2,
                        "internal": m.internal,
                        "end_sem": m.end_sem,
                    }
                    score = compute_subject_score(comps)
                except Exception:
                    score = None

            if score is None:
                continue  # skip students with no data for this subject

            # accumulate
            subject_sum[sub_code] = subject_sum.get(sub_code, 0.0) + float(score)
            subject_count[sub_code] = subject_count.get(sub_code, 0) + 1
            subject_pass[sub_code] = subject_pass.get(sub_code, 0) + (1 if float(score) >= 40.0 else 0)

            if sub_code not in subject_name_map:
                subj = Subject.query.filter_by(sub_code=sub_code).first()
                subject_name_map[sub_code] = subj.sub_name if subj else sub_code

    # build cards and chart arrays
    cards = []
    labels = []
    values = []
    for sub_code, total in subject_sum.items():
        count = subject_count.get(sub_code, 0)
        if count == 0:
            continue
        avg = round(total / count, 2)  # average percent
        pass_count = subject_pass.get(sub_code, 0)
        pass_rate = round((pass_count / count) * 100.0, 2) if count else 0.0

        cards.append({
            "sub_code": sub_code,
            "sub_name": subject_name_map.get(sub_code, sub_code),
            "average": avg,
            "pass_rate": pass_rate,
            "count": count
        })
        labels.append(f"{subject_name_map.get(sub_code, sub_code)} ({sub_code})")
        values.append(avg)

    # sort cards by average descending for nicer UI
    cards.sort(key=lambda x: x["average"] if x["average"] is not None else -1, reverse=True)

    return jsonify({
        "branch": branch,
        "year": year_i,
        "semester": sem_i,
        "cards": cards,
        "chart": {
            "labels": labels,
            "values": values
        }
    })


@results_bp.route("/graphs/risk_distribution")
def risk_distribution_graph():
    """
    Returns a pie-chart-ready JSON for risk distribution for a batch:
    - counts: dict with counts for low/medium/high/unknown
    - labels: ordered list ['Low', 'Medium', 'High', 'Unknown']
    - values: list of counts matching labels
    - percentages: percentages per label (rounded 2 decimals)
    Required query params: branch, year, semester
    """
    branch = (request.args.get("branch") or "").strip()
    year = request.args.get("year")
    semester = request.args.get("semester")

    if not branch or not year or not semester:
        return jsonify({"error": "branch, year, semester required"}), 400

    year_i, sem_i = int(year), int(semester)
    students = Student.query.filter_by(branch=branch, exam_year=year_i).all()

    counts = {"low": 0, "medium": 0, "high": 0, "unknown": 0}
    total = 0

    for s in students:
        # compute overall for the semester
        overall, _, _ = _compute_student_score_for_sem(s, sem_i)
        if overall is None:
            counts["unknown"] += 1
        else:
            r = (map_risk(overall) or "unknown").lower()
            if r not in counts:
                counts[r] = counts.get(r, 0) + 1
            else:
                counts[r] += 1
        total += 1

    # prepare labels/values in consistent order
    ordered = [("low", "Low"), ("medium", "Medium"), ("high", "High"), ("unknown", "Unknown")]
    labels = [label for _, label in ordered]
    values = [counts.get(key, 0) for key, _ in ordered]
    percentages = [round((v / total * 100), 2) if total else 0.0 for v in values]

    return jsonify({
        "branch": branch,
        "year": year_i,
        "semester": sem_i,
        "total_students": total,
        "counts": counts,
        "labels": labels,
        "values": values,
        "percentages": percentages
    })



@results_bp.route("/graphs/sgpa_trend")
def sgpa_trend_graph():
    pin = (request.args.get("pin") or "").strip()
    if not pin:
        return jsonify({"error": "pin required"}), 400

    student = Student.query.filter_by(pin=pin).first()
    if not student:
        return jsonify({"error": "Student not found"}), 404

    trend = []
    semesters = sorted({m.semester for m in Mark.query.filter_by(student_id=student.id).all()})
    for sem in semesters:
        overall, _, _ = _compute_student_score_for_sem(student, sem)
        trend.append({"semester": sem, "overall_score": overall})

    return jsonify({
        "student": {"pin": student.pin, "name": student.name, "branch": student.branch},
        "trend": trend
    })
