# app/results/routes.py
"""
Consolidated Results routes.

This file merges the previous results implementation with:
 - uploader-scoped visibility (faculty only see marks they uploaded; admin sees all)
 - grade & pass/fail computation
 - feedback generation (uses generate_feedback if available)
 - defensive fallbacks when utility functions are missing or have different signatures

Blueprint URL prefix: /api/results
"""

import re
from flask import Blueprint, request, jsonify, Response
from io import StringIO
import csv
from typing import Optional, Tuple, List, Dict, Any

from app import db
from app.models import Student, Mark, Subject, UploadedFile, Institution

# Prefer utilsss (your older utilities). If not present, fall back to app.utils.grades
try:
    from app.utilsss import compute_subject_score, compute_overall_score, map_risk, generate_feedback
except Exception:
    # fallback implementations / imports
    try:
        from app.utils.grades import compute_subject_score as _compute_subject_score_fallback
    except Exception:
        _compute_subject_score_fallback = None

    def compute_subject_score(components: Dict[str, Optional[float]], absent_map: Optional[Dict[str, bool]] = None) -> Optional[float]:
        """
        Fallback subject scoring:
        - If a dedicated implementation exists in app.utils.grades, try calling it.
        - Otherwise compute a simple weighted score with rescale semantics:
          SubjectScore = 0.2*M1% + 0.2*M2% + 0.2*Internal% + 0.4*End%
          Rescale rule: if some components are missing (None) because exam not held, rescale remaining weights proportionally.
          Absent components (explicit) should be provided via absent_map (True => treat as 0 and do NOT rescale).
        """
        # helpers
        def pct(val, out_of):
            return (float(val) / out_of) * 100.0 if val is not None else None

        if _compute_subject_score_fallback:
            # try to call fallback; its signature might accept 2 args or 1 arg
            try:
                if absent_map is not None:
                    return _compute_subject_score_fallback(components, absent_map)
                return _compute_subject_score_fallback(components)
            except TypeError:
                try:
                    return _compute_subject_score_fallback(components)
                except Exception:
                    pass

        # custom lightweight implementation
        # Map components to percentages
        m1 = components.get("mid1")
        m2 = components.get("mid2")
        internal = components.get("internal")
        end_sem = components.get("end_sem")

        # Identify explicit absents (absent_map True) vs missing (None but not absent)
        absent = {k: False for k in ("mid1", "mid2", "internal", "end_sem")}
        if absent_map:
            for k in absent_map:
                absent[k] = bool(absent_map.get(k, False))
        else:
            # If stored as 0.0 we treat as absent only when caller indicates; here we won't assume 0 is absent
            pass

        # Convert to percent where present
        comps_pct = {
            "mid1": pct(m1, 20) if m1 is not None else None,
            "mid2": pct(m2, 20) if m2 is not None else None,
            "internal": pct(internal, 20) if internal is not None else None,
            "end_sem": pct(end_sem, 40) if end_sem is not None else None
        }

        # Determine which components are "present" for rescale (present means not missing and not an explicit absent)
        present = {k: (comps_pct[k] is not None and not absent.get(k, False)) for k in comps_pct}

        # Base weights
        weights = {"mid1": 0.2, "mid2": 0.2, "internal": 0.2, "end_sem": 0.4}
        # For explicit absent (absent=True), treat value as 0 and DO NOT rescale (weight remains assigned but value=0)
        # For missing (value None), exclude and rescale remaining present (not absent) weights
        # Calculate effective weights
        effective_weights = {}
        total_present_weight = 0.0
        for k in weights:
            if comps_pct[k] is None and not absent.get(k, False):
                # missing, skip
                effective_weights[k] = 0.0
            else:
                # present or absent (absent keeps weight)
                effective_weights[k] = weights[k]
                total_present_weight += weights[k]

        if total_present_weight == 0:
            return None

        # Rescale weights so sum to 1 but do NOT rescale weights for components that were absent? 
        # According to rules: if component missing because exam not held -> rescale remaining base weights proportionally.
        # If component absent -> treat as 0 and DO NOT rescale.
        # Our effective_weights currently includes absent components with their weight; we need to rescale only if there are missing components
        missing_exists = any(comps_pct[k] is None and not absent.get(k, False) for k in comps_pct)
        final_weights = {}
        if missing_exists:
            # sum weights of components that are not missing (including absents)
            sum_active = sum([weights[k] for k in weights if not (comps_pct[k] is None and not absent.get(k, False))])
            # rescale active weights to sum to 1
            for k in weights:
                if comps_pct[k] is None and not absent.get(k, False):
                    final_weights[k] = 0.0
                else:
                    # rescale proportionally
                    final_weights[k] = weights[k] / sum_active if sum_active > 0 else 0.0
        else:
            # normal case: all components present or absent - no rescale
            for k in weights:
                final_weights[k] = weights[k]

        # compute score using percent values; treat explicit absent as 0
        score = 0.0
        for k in ("mid1", "mid2", "internal", "end_sem"):
            val_pct = comps_pct[k]
            if val_pct is None:
                # missing component contributes 0
                continue
            # if explicit absent -> value is 0
            if absent.get(k, False):
                contribution = 0.0
            else:
                contribution = (val_pct * final_weights[k])
            score += contribution

        return round(score, 2)

    def compute_overall_score(scores: List[float]) -> Optional[float]:
        if not scores:
            return None
        return round(sum(scores) / len(scores), 2)

    def map_risk(overall: Optional[float]) -> Optional[str]:
        if overall is None:
            return None
        if overall < 40:
            return "High"
        if overall < 60:
            return "Medium"
        return "Low"

    def generate_feedback(name: str, overall: Optional[float], risk_subjects: List[str], avg_attendance: Optional[float]) -> str:
        # Deterministic simple feedback template
        if overall is None:
            return f"No sufficient data for {name} to generate feedback."
        parts = []
        if overall >= 70:
            parts.append("Strong overall performance. Keep it up.")
        elif overall >= 50:
            parts.append("Average performance — focus on weak subjects to improve.")
        else:
            parts.append("Critical: performance is low. Immediate attention needed.")
        if risk_subjects:
            parts.append("Weak subjects: " + ", ".join(risk_subjects) + ".")
        if avg_attendance is not None and avg_attendance < 75:
            parts.append("Attendance below 75% — address attendance.")
        return " ".join(parts)

# Flask login
from flask_login import login_required, current_user

results_bp = Blueprint("results", __name__, url_prefix="/api/results")


# -------------------------
# Helpers & validators
# -------------------------
PIN_REGEX = re.compile(r'^\s*\d{2,}-[A-Za-z0-9]+-\d+\s*$', re.IGNORECASE)


def _mark_query_for_user():
    """Return a base query for Mark records visible to current_user."""
    try:
        if getattr(current_user, "role", None) == "admin":
            return Mark.query
    except Exception:
        return Mark.query

    # Non-admin faculty — only see marks from files they uploaded
    return (
        Mark.query.join(UploadedFile, Mark.uploaded_file_id == UploadedFile.id)
        .filter(UploadedFile.uploaded_by == current_user.id)
        .with_entities(Mark)  # 👈 ensures later filters apply to Mark model
    )


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


def _compute_student_score_for_sem(student: Student, semester: int):
    """
    Returns: (overall_score: Optional[float], subject_count: int, details: List[dict])
    Each detail contains per-subject raw components, computed subject_score, risk, attendance,
    and includes 'grade' and 'result' fields as well.
    """
    marks = _mark_query_for_user().filter(
    Mark.student_id == student.id,
    Mark.semester == semester
    ).all()

    details = []
    scores = []

    for m in marks:
        subj_obj = Subject.query.filter_by(sub_code=m.sub_code).first()
        sub_name = subj_obj.sub_name if subj_obj else ""

        # Build components
        comps = {
            "mid1": getattr(m, "mid1", None),
            "mid2": getattr(m, "mid2", None),
            "internal": getattr(m, "internal", None),
            "end_sem": getattr(m, "end_sem", None),
            "attendance": getattr(m, "attendance", None)
        }

        # Deduce absent_map: our commit flow stores explicit absent as 0.0
        absent_map = {
            "mid1": (comps["mid1"] is not None and float(comps["mid1"]) == 0.0),
            "mid2": (comps["mid2"] is not None and float(comps["mid2"]) == 0.0),
            "internal": (comps["internal"] is not None and float(comps["internal"]) == 0.0),
            "end_sem": (comps["end_sem"] is not None and float(comps["end_sem"]) == 0.0),
        }

        # Try stored subject_score else compute
        ss = getattr(m, "subject_score", None)
        if ss is None:
            # Try calling compute_subject_score with signature compatibility
            try:
                # Many older implementations accept only components dict
                try:
                    ss = compute_subject_score(comps)
                except TypeError:
                    # Some implementations expect (components, absent_map)
                    ss = compute_subject_score(comps, absent_map)
            except Exception:
                ss = None

        if ss is not None:
            try:
                scores.append(float(ss))
            except Exception:
                pass

        # Determine risk for this subject using mid/end rules if stored flags exist
        risk_flag = getattr(m, "risk", None)
        # compute grade/result based on subject_score
        grade, result = compute_grade_and_result(ss)

        details.append({
            "sub_code": m.sub_code,
            "sub_name": sub_name,
            "mid1": comps["mid1"],
            "mid2": comps["mid2"],
            "internal": comps["internal"],
            "end_sem": comps["end_sem"],
            "total": getattr(m, "total", None),
            "attendance": comps.get("attendance"),
            "subject_score": ss,
            "risk": risk_flag,
            "grade": grade,
            "result": result
        })

    # Compute overall using compute_overall_score if available
    overall = None
    try:
        overall = compute_overall_score(scores) if scores else None
    except Exception:
        # fallback average
        if scores:
            overall = round(sum(scores) / len(scores), 2)
        else:
            overall = None

    return overall, len(details), details


# -------------------------
# 1) Search / listing
# -------------------------
@results_bp.route("/search")
@login_required
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
            # show marks grouped by semester (use uploader-scoped marks)
            marks_by_sem = {}
            marks = _mark_query_for_user().filter_by(student_id=student.id).order_by(Mark.semester).all()
            for m in marks:
                key = str(m.semester)
                marks_by_sem.setdefault(key, []).append({
                    "sub_code": m.sub_code,
                    "mid1": m.mid1,
                    "mid2": m.mid2,
                    "internal": m.internal,
                    "end_sem": m.end_sem,
                    "total": getattr(m, "total", None),
                    "attendance": m.attendance,
                    "subject_score": getattr(m, "subject_score", None),
                    "risk": getattr(m, "risk", None),
                    "grade": compute_grade_and_result(getattr(m, "subject_score", None))[0],
                    "result": compute_grade_and_result(getattr(m, "subject_score", None))[1]
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

        # Prepare risk subjects (subject names) where subject_score < 40
        risk_subjects = [d["sub_name"] or d["sub_code"] for d in details if d.get("subject_score") is not None and float(d["subject_score"]) < 40.0]
        atts = [d.get("attendance") for d in details if d.get("attendance") is not None]
        avg_attendance = (sum(atts) / len(atts)) if atts else None

        # Use generate_feedback if available
        try:
            feedback = generate_feedback(student.name, overall, risk_subjects, avg_attendance)
        except Exception:
            feedback = generate_feedback(student.name, overall, risk_subjects, avg_attendance) if callable(generate_feedback) else ""

            # Build semester object so frontend can consume either `semesters` or top-level fields
            semester_obj = {
                "semester": sem,
                "overall_score": overall,
                "subject_count": count,
                "subjects": details,
                "attendance": avg_attendance,
                "feedback": feedback
            }

            # Also include feedback inside student object (frontend checks student.feedback)
            student_obj = {
                "pin": student.pin,
                "name": student.name,
                "branch": student.branch,
                "exam_year": student.exam_year,
                "feedback": feedback
            }

            # Optional: include trend if you want (sgpa_trend_graph can be used).
            # For now we'll return an empty trend array — frontend will still show graph placeholders.
            trend = []

            return jsonify({
                "student": student_obj,
                "semester": sem,
                "semesters": [semester_obj],   # frontend expects 'semesters' list
                "overall_score": overall,
                "subject_count": count,
                "subjects": details,
                "attendance": avg_attendance,
                "feedback": feedback,         # keep compatibility (top-level feedback too)
                "trend": trend
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
    temp_rows = []
    batch_scores = []
    sem = int(semester) if semester and semester.isdigit() else None

    for s in pagination.items:
        # skip invalid or placeholder rows
        if not _is_pin_valid(s.pin):
            continue
        if s.name and 'polytechnic' in s.name.lower():
            continue

        overall, subj_count, details = None, 0, []
        attendance_val = None

        # If semester filter provided, compute per-student details
        if sem:
            overall, subj_count, details = _compute_student_score_for_sem(s, sem)
            atts = [d.get("attendance") for d in details if d.get("attendance") is not None]
            if atts:
                attendance_val = sum(atts) / len(atts)

        # --- NEW: generate feedback for the student (for batch listing) ---
                # --- Generate feedback for every student (even when data missing) ---
        try:
            risk_subjects = [
                (d.get("sub_name") or d.get("sub_code"))
                for d in details
                if d.get("subject_score") is not None and float(d.get("subject_score")) < 40.0
            ]
        except Exception:
            risk_subjects = []

        # Always call generate_feedback — it will handle None safely
        try:
            feedback = generate_feedback(s.name, overall, risk_subjects, attendance_val) if callable(generate_feedback) else ""
        except Exception as e:
            print("⚠️ feedback generation error for", s.pin, ":", e)
            feedback = "Feedback unavailable due to internal error."



        temp_rows.append({
            "pin": s.pin,
            "name": s.name,
            "branch": s.branch,
            "exam_year": s.exam_year,
            "attendance": attendance_val,
            "overall_score": overall,
            "subject_count": subj_count,
            "risk": map_risk(overall) if overall is not None else None,
            "feedback": feedback
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
@login_required
def batch_overview():
    branch = (request.args.get("branch") or "").strip()
    exam_year = request.args.get("year")
    semester = request.args.get("semester")

    if not branch or not exam_year or not semester:
        return jsonify({"error": "branch, year and semester required"}), 400

    year_i, sem_i = int(exam_year), int(semester)
    students = Student.query.filter_by(branch=branch, exam_year=year_i).all()

    risk_counts = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
    overall_vals = []
    attendance_vals = []

    for s in students:
        if not _is_pin_valid(s.pin):
            continue
        overall, _, details = _compute_student_score_for_sem(s, sem_i)
        if overall is None:
            risk_counts["unknown"] += 1
        else:
            r = map_risk(overall) or "unknown"
            risk_counts[r.lower()] = risk_counts.get(r.lower(), 0) + 1
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
@login_required
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

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["PIN", "Name", "Branch", "ExamYear", "Attendance%", "OverallScore", "Risk"])

    for s in students:
        if not _is_pin_valid(s.pin):
            continue
        overall, _, details = (None, 0, [])
        overall_att = None
        if sem_i:
            overall, _, details = _compute_student_score_for_sem(s, sem_i)
            atts = [d.get("attendance") for d in details if d.get("attendance") is not None]
            if atts:
                overall_att = sum(atts) / len(atts)
        writer.writerow([s.pin, s.name, s.branch, s.exam_year, overall_att or "", overall or "", map_risk(overall) or ""])

    csv_data = output.getvalue()
    output.close()
    return Response(csv_data, mimetype="text/csv",
                    headers={"Content-disposition": f"attachment; filename=students_export_{branch}_{exam_year}_{semester}.csv"})


# -------------------------
# Institution
# -------------------------
@results_bp.route("/institution")
@login_required
def get_institution():
    inst = Institution.query.first()
    return jsonify({"name": inst.name if inst else ""})


# -------------------------
# Graph endpoints
# -------------------------
@results_bp.route("/graphs/subject_averages")
@login_required
def subject_averages_graph():
    branch = (request.args.get("branch") or "").strip()
    year = request.args.get("year")
    semester = request.args.get("semester")

    if not branch or not year or not semester:
        return jsonify({"error": "branch, year, semester required"}), 400

    year_i, sem_i = int(year), int(semester)
    students = Student.query.filter_by(branch=branch, exam_year=year_i).all()

    subject_sum = {}
    subject_count = {}
    subject_pass = {}
    subject_name_map = {}

    for s in students:
        marks = _mark_query_for_user().filter_by(student_id=s.id, semester=sem_i).all()
        for m in marks:
            sub_code = m.sub_code
            score = getattr(m, "subject_score", None)
            if score is None:
                try:
                    comps = {
                        "attendance": m.attendance,
                        "mid1": m.mid1,
                        "mid2": m.mid2,
                        "internal": m.internal,
                        "end_sem": m.end_sem,
                    }
                    # deduce absent_map: stored 0.0 are explicit absents
                    absent_map = {
                        "mid1": (comps["mid1"] is not None and float(comps["mid1"]) == 0.0),
                        "mid2": (comps["mid2"] is not None and float(comps["mid2"]) == 0.0),
                        "internal": (comps["internal"] is not None and float(comps["internal"]) == 0.0),
                        "end_sem": (comps["end_sem"] is not None and float(comps["end_sem"]) == 0.0),
                    }
                    score = compute_subject_score(comps, absent_map) if getattr(compute_subject_score, "__code__", None) else compute_subject_score(comps)
                except Exception:
                    score = None

            if score is None:
                continue

            subject_sum[sub_code] = subject_sum.get(sub_code, 0.0) + float(score)
            subject_count[sub_code] = subject_count.get(sub_code, 0) + 1
            subject_pass[sub_code] = subject_pass.get(sub_code, 0) + (1 if float(score) >= 40.0 else 0)

            if sub_code not in subject_name_map:
                subj = Subject.query.filter_by(sub_code=sub_code).first()
                subject_name_map[sub_code] = subj.sub_name if subj else sub_code

    cards = []
    labels = []
    values = []
    for sub_code, total in subject_sum.items():
        count = subject_count.get(sub_code, 0)
        if count == 0:
            continue
        avg = round(total / count, 2)
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
@login_required
def risk_distribution_graph():
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
        overall, _, _ = _compute_student_score_for_sem(s, sem_i)
        if overall is None:
            counts["unknown"] += 1
        else:
            r = (map_risk(overall) or "unknown").lower()
            counts[r] = counts.get(r, 0) + 1
        total += 1

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
@login_required
def sgpa_trend_graph():
    pin = (request.args.get("pin") or "").strip()
    if not pin:
        return jsonify({"error": "pin required"}), 400

    student = Student.query.filter_by(pin=pin).first()
    if not student:
        return jsonify({"error": "Student not found"}), 404

    # Determine semesters visible to this user for this student
    sems = sorted({m.semester for m in _mark_query_for_user().filter_by(student_id=student.id).all()})
    trend = []
    for sem in sems:
        overall, _, _ = _compute_student_score_for_sem(student, sem)
        trend.append({"semester": sem, "overall_score": overall})

    return jsonify({
        "student": {"pin": student.pin, "name": student.name, "branch": student.branch},
        "trend": trend
    })
