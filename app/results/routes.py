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
from flask import current_app

from app import db
from app.models import Student, Mark, Subject, UploadedFile, Institution

# add import for stats model
from app.models import StudentSemesterStat
from datetime import datetime

def upsert_student_semester_stat(student_id: int, semester: int, exam_year: Optional[int], overall: Optional[float], risk_str: Optional[str]):
    """Idempotent upsert for student_semester_stats."""
    try:
        stat = StudentSemesterStat.query.filter_by(student_id=student_id, semester=semester).first()
        if stat:
            stat.overall_score = overall
            stat.risk = risk_str
            stat.exam_year = exam_year
            stat.computed_on = datetime.utcnow()
        else:
            stat = StudentSemesterStat(
                student_id=student_id,
                semester=semester,
                exam_year=exam_year,
                overall_score=overall,
                risk=risk_str,
                computed_on=datetime.utcnow()
            )
            db.session.add(stat)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to upsert student_semester_stat for %s sem %s", student_id, semester)


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
            return "high"
        if overall < 60:
            return "medium"
        return "low"

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
    # Use LEFT OUTER JOIN: include marks that have no uploaded_file_id (NULL)
    # Reason: some DB rows (seeded / imported) have uploaded_file_id = NULL and
    # should still be visible for reporting pages. We still keep the filter to
    # allow faculty to see marks that they uploaded, but include NULL-uploaded
    # marks as well (backwards-compatible for seeded data).
    try:
        return (
            Mark.query.outerjoin(UploadedFile, Mark.uploaded_file_id == UploadedFile.id)
            .filter(
                db.or_(
                    UploadedFile.uploaded_by == current_user.id,
                    Mark.uploaded_file_id == None  # include seeded / legacy rows
                )
            )
            .with_entities(Mark)
        )
    except Exception:
        # defensive fallback: return all marks if ORM expression fails
        return Mark.query


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

    - Always recomputes subject_score from mid1/mid2/internal/end_sem using compute_subject_score
      (so it does NOT depend on marks.subject_score or marks.risk being filled in DB).
    """
    marks = _mark_query_for_user().filter(
        Mark.student_id == student.id,
        Mark.semester == semester
    ).all()

    details: List[Dict[str, Any]] = []
    scores: List[float] = []

    for m in marks:
        subj_obj = Subject.query.filter_by(sub_code=m.sub_code).first()
        sub_name = subj_obj.sub_name if subj_obj else ""

        # raw components
        mid1 = getattr(m, "mid1", None)
        mid2 = getattr(m, "mid2", None)
        internal = getattr(m, "internal", None)
        end_sem = getattr(m, "end_sem", None)
        attendance = getattr(m, "attendance", None)

        comps = {
            "mid1": mid1,
            "mid2": mid2,
            "internal": internal,
            "end_sem": end_sem,
        }

        # 0.0 in DB = absent
        absent_flags = {
            "mid1": (mid1 is not None and float(mid1) == 0.0),
            "mid2": (mid2 is not None and float(mid2) == 0.0),
            "internal": (internal is not None and float(internal) == 0.0),
            "end_sem": (end_sem is not None and float(end_sem) == 0.0),
        }

        # 🔹 Prefer stored subject_score from DB if available
        ss = None
        stored_score = getattr(m, "subject_score", None)
        if stored_score is not None:
            try:
                ss = float(stored_score)
            except Exception:
                ss = None

        # 🔹 If not stored, fall back to computing it
        if ss is None:
            try:
                ss = compute_subject_score(comps, absent_flags)
            except TypeError:
                ss = compute_subject_score(comps)
            except Exception:
                ss = None


        if ss is not None:
            try:
                scores.append(float(ss))
            except Exception:
                pass

        # grade & pass/fail from score
        grade, result = compute_grade_and_result(ss)

        # we don't depend on DB risk; Student Report / detail modal
        # recomputes per-subject risk in frontend from the score anyway.
        risk_flag = getattr(m, "risk", None)

        details.append({
            "sub_code": m.sub_code,
            "sub_name": sub_name,
            "mid1": mid1,
            "mid2": mid2,
            "internal": internal,
            "end_sem": end_sem,
            "total": getattr(m, "total", None),
            "attendance": attendance,
            "subject_score": ss,
            "risk": risk_flag,
            "grade": grade,
            "result": result,
        })

    # overall = average of subject scores
    try:
        overall = compute_overall_score(scores) if scores else None
    except Exception:
        overall = round(sum(scores) / len(scores), 2) if scores else None

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
    semester_arg = request.args.get("semester")

    # ------------------------------------------------------------------
    # 1) SINGLE STUDENT MODE (pin given)
    # ------------------------------------------------------------------
    if pin:
        student = Student.query.filter_by(pin=pin).first()
        if not student:
            return jsonify({"error": "Student not found"}), 404

        sem = int(semester_arg) if semester_arg and semester_arg.isdigit() else None

               # --- A) pin given, but NO specific semester -> grouped marks by semester
        if sem is None:
            marks_by_sem = {}
            semester_scores: Dict[str, List[float]] = {}
            semester_attendance: Dict[str, List[float]] = {}

            marks = (
                _mark_query_for_user()
                .filter_by(student_id=student.id)
                .order_by(Mark.semester)
                .all()
            )

            # cache subject names to avoid querying Subject table repeatedly
            subject_name_cache: Dict[str, str] = {}

            for m in marks:
                key = str(m.semester)
                sub_code = m.sub_code

                # look up subject name
                if sub_code in subject_name_cache:
                    sub_name = subject_name_cache[sub_code]
                else:
                    subj_obj = Subject.query.filter_by(sub_code=sub_code).first()
                    sub_name = subj_obj.sub_name if subj_obj else sub_code
                    subject_name_cache[sub_code] = sub_name

                # subject score: prefer stored value
                stored_score = getattr(m, "subject_score", None)
                try:
                    ss = float(stored_score) if stored_score is not None else None
                except Exception:
                    ss = None

                grade, result = compute_grade_and_result(ss)

                row = {
                    "sub_code": sub_code,
                    "sub_name": sub_name,
                    "mid1": m.mid1,
                    "mid2": m.mid2,
                    "internal": m.internal,
                    "end_sem": m.end_sem,
                    "total": getattr(m, "total", None),
                    "attendance": m.attendance,
                    "subject_score": ss,
                    "risk": getattr(m, "risk", None),
                    "grade": grade,
                    "result": result,
                }

                marks_by_sem.setdefault(key, []).append(row)

                # collect for per-semester aggregates
                if ss is not None:
                    semester_scores.setdefault(key, []).append(float(ss))
                if m.attendance is not None:
                    semester_attendance.setdefault(key, []).append(float(m.attendance))

            # build "semesters" array that React expects, with overall_score filled
            semesters = []
            for key, rows in marks_by_sem.items():
                sem_num = int(key)
                scores = semester_scores.get(key, []) or []
                overall = None
                if scores:
                    try:
                        overall = round(sum(scores) / len(scores), 2)
                    except Exception:
                        overall = None

                # Prefer cached score from StudentSemesterStat if present
                try:
                    stat = StudentSemesterStat.query.filter_by(
                        student_id=student.id,
                        semester=sem_num
                    ).first()
                except Exception:
                    stat = None

                if stat and stat.overall_score is not None:
                    try:
                        overall = float(stat.overall_score)
                    except Exception:
                        pass

                atts = semester_attendance.get(key, []) or []
                avg_attendance = sum(atts) / len(atts) if atts else None

                # risk subjects for feedback
                risk_subjects = []
                for r in rows:
                    try:
                        if r.get("subject_score") is not None and float(r["subject_score"]) < 40.0:
                            risk_subjects.append(r.get("sub_name") or r.get("sub_code"))
                    except Exception:
                        continue

                try:
                    feedback = generate_feedback(
                        student.name,
                        overall,
                        risk_subjects,
                        avg_attendance,
                    ) if callable(generate_feedback) else ""
                except Exception:
                    feedback = "Feedback unavailable due to internal error."

                semesters.append({
                    "semester": sem_num,
                    "subjects": rows,
                    "overall_score": overall,
                    "attendance": avg_attendance,
                    "feedback": feedback,
                })

            # sort semesters nicely
            semesters.sort(key=lambda s: s["semester"])

            return jsonify({
                "student": {
                    "pin": student.pin,
                    "name": student.name,
                    "branch": student.branch,
                    "exam_year": student.exam_year,
                },
                "marks_by_semester": marks_by_sem,  # kept for backward compatibility
                "semesters": semesters,            # ✅ new, with overall_score
            })



        # --- B) pin + semester -> one semester detail (used by Student Report modal)
        overall, count, details = _compute_student_score_for_sem(student, sem)
        # 🔹 Prefer cached overall from student_semester_stats if available
        try:
            stat = StudentSemesterStat.query.filter_by(student_id=student.id, semester=sem).first()
        except Exception:
            stat = None

        if stat and stat.overall_score is not None:
            try:
                overall = float(stat.overall_score)
            except Exception:
                pass


        # subjects with score < 40 are considered risk subjects
        risk_subjects = [
            (d.get("sub_name") or d.get("sub_code"))
            for d in details
            if d.get("subject_score") is not None
            and float(d.get("subject_score")) < 40.0
        ]

        atts = [d.get("attendance") for d in details if d.get("attendance") is not None]
        avg_attendance = (sum(atts) / len(atts)) if atts else None

        try:
            feedback = generate_feedback(
                student.name,
                overall,
                risk_subjects,
                avg_attendance,
            ) if callable(generate_feedback) else ""
        except Exception:
            feedback = "Feedback unavailable due to internal error."

        semester_obj = {
            "semester": sem,
            "overall_score": overall,
            "subject_count": count,
            "subjects": details,
            "attendance": avg_attendance,
            "feedback": feedback,
        }

        student_obj = {
            "pin": student.pin,
            "name": student.name,
            "branch": student.branch,
            "exam_year": student.exam_year,
            "feedback": feedback,
        }

        # simple trend: overall per semester for this student
        trend = []
        sems_available = sorted({
            m.semester
            for m in _mark_query_for_user().filter_by(student_id=student.id).all()
        })
        for s_sem in sems_available:
            ov, _, _ = _compute_student_score_for_sem(student, s_sem)
            trend.append({"semester": s_sem, "overall_score": ov})

        # IMPORTANT: this shape matches what student-report JS expects:
        # - top-level overall_score
        # - top-level subjects[]
        return jsonify({
            "student": student_obj,
            "semester": sem,
            
            # 👇 required for student-report.js
            "pin": student.pin,
            "name": student.name,
            "branch": student.branch,
            "year": student.exam_year,

            # display fields expected by frontend
            "overall": overall,
            "overall_score": overall,
            "risk": map_risk(overall),
            "risk_status": map_risk(overall),
            
            "subject_count": count,
            "subjects": details,
            "attendance": avg_attendance,
            "feedback": feedback,
            "trend": trend,
        })


    # ------------------------------------------------------------------
    # 2) BATCH LISTING MODE (no pin, used by Student Report table)
    # ------------------------------------------------------------------
    page = int(request.args.get("page") or 1)
    per_page = int(request.args.get("per_page") or 50)
    sort = (request.args.get("sort") or "pin").lower()
    order = (request.args.get("order") or "asc").lower()

    query = Student.query
    if branch:
        query = query.filter_by(branch=branch)
    # ⛔ Do NOT filter by exam_year here, because all students currently have exam_year=2024
    # if exam_year and exam_year.isdigit():
    #     query = query.filter_by(exam_year=int(exam_year))
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Student.pin.ilike(like),
                Student.name.ilike(like),
            )
        )


    students = query.order_by(Student.pin).all()

    temp_rows = []
    batch_scores = []
    sem = int(semester_arg) if semester_arg and semester_arg.isdigit() else None

    for s in students:
        # skip invalid / header rows
        if not _is_pin_valid(s.pin):
            continue
        if s.name and "polytechnic" in s.name.lower():
            continue

        overall = None
        subj_count = 0
        details = []
        attendance_val = None

        if sem:
            # Try to use pre-computed value from student_semester_stats
            try:
                stat = StudentSemesterStat.query.filter_by(student_id=s.id, semester=sem).first()
            except Exception:
                stat = None

            if stat and stat.overall_score is not None:
                overall = float(stat.overall_score)
                # we still compute details to show attendance/subjects if required
                try:
                    _, subj_count, details = _compute_student_score_for_sem(s, sem)
                except Exception:
                    subj_count = 0
                    details = []
            else:
                overall, subj_count, details = _compute_student_score_for_sem(s, sem)
                # persist computed stat (best-effort)
                try:
                    upsert_student_semester_stat(s.id, sem, s.exam_year, overall, map_risk(overall) if overall is not None else None)
                except Exception:
                    current_app.logger.exception("Failed to upsert stat for student %s sem %s", s.pin, sem)

            # compute average attendance for this student for this sem
            atts = [d.get("attendance") for d in details if d.get("attendance") is not None]
            if atts:
                attendance_val = sum(atts) / len(atts)


        # risk subjects for feedback
        risk_subjects = []
        for d in details:
            try:
                if d.get("subject_score") is not None and float(d.get("subject_score")) < 40.0:
                    risk_subjects.append(d.get("sub_name") or d.get("sub_code"))
            except Exception:
                continue

        try:
            feedback = generate_feedback(
                s.name,
                overall,
                risk_subjects,
                attendance_val,
            ) if callable(generate_feedback) else ""
        except Exception:
            feedback = "Feedback unavailable due to internal error."

        temp_rows.append({
            "pin": s.pin,
            "name": s.name,
            "branch": s.branch,
            "exam_year": s.exam_year,
            "attendance": attendance_val,
            "overall_score": overall,                     # <- used by student-report.html
            "subject_count": subj_count,
            "risk": map_risk(overall) if overall is not None else None,  # <- used by student-report.html
            "feedback": feedback,
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
        "items": temp_rows,
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

    q = Student.query
    if branch:
        q = q.filter_by(branch=branch)
    students = q.all()
    risk_counts = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
    overall_vals = []
    attendance_vals = []
    valid_students = 0          # 👈 add this

    for s in students:
        # skip invalid/header rows
        if not _is_pin_valid(s.pin):
            continue

        valid_students += 1    # 👈 count only valid ones

        overall, _, details = _compute_student_score_for_sem(s, sem_i)
        if overall is None:
            risk_counts["unknown"] += 1
        else:
            r = (map_risk(overall) or "unknown").lower()
            risk_counts[r] = risk_counts.get(r, 0) + 1
            overall_vals.append(overall)

        atts = [d.get("attendance") for d in details if d.get("attendance") is not None]
        if atts:
            attendance_vals.append(sum(atts) / len(atts))

    avg_attendance = (sum(attendance_vals) / len(attendance_vals)) if attendance_vals else None
    avg_performance = (sum(overall_vals) / len(overall_vals)) if overall_vals else None

    return jsonify({
        "branch": branch,
        "year": year_i,
        "semester": sem_i,
        "total_students": valid_students,        # 👈 use valid count
        "risk_counts": risk_counts,
        "avg_attendance": avg_attendance,
        "avg_class_performance": avg_performance,
        "class_average": avg_performance,
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
@login_required   # keep it commented if you want public access
def subject_averages_graph():
    branch = (request.args.get("branch") or "").strip()
    year = request.args.get("year")
    semester = request.args.get("semester")

    if not branch or not year or not semester:
        return jsonify({"error": "branch, year, semester required"}), 400

    year_i, sem_i = int(year), int(semester)

    # IMPORTANT:
    # Do NOT scope by current_user here. Graphs are for the whole branch.
    # We join Student to get only the selected branch, then filter by semester.
    marks = (
        Mark.query
        .join(Student, Mark.student_id == Student.id)
        .filter(
            Student.branch == branch,
            Mark.semester == sem_i,
            Mark.year == year_i,          # ✅ use the selected exam year
        )
        .all()
    )


    subject_sum: Dict[str, float] = {}
    subject_count: Dict[str, int] = {}
    subject_pass: Dict[str, int] = {}
    subject_name_map: Dict[str, str] = {}

    for m in marks:
        sub_code = m.sub_code

        # subject score: prefer stored value
        score = getattr(m, "subject_score", None)
        if score is None:
            try:
                comps = {
                    "mid1": m.mid1,
                    "mid2": m.mid2,
                    "internal": m.internal,
                    "end_sem": m.end_sem,
                }
                absent_map = {
                    "mid1": (m.mid1 is not None and float(m.mid1) == 0.0),
                    "mid2": (m.mid2 is not None and float(m.mid2) == 0.0),
                    "internal": (m.internal is not None and float(m.internal) == 0.0),
                    "end_sem": (m.end_sem is not None and float(m.end_sem) == 0.0),
                }
                score = compute_subject_score(comps, absent_map)
            except Exception:
                score = None

        if score is None:
            continue

        score = float(score)
        subject_sum[sub_code] = subject_sum.get(sub_code, 0.0) + score
        subject_count[sub_code] = subject_count.get(sub_code, 0) + 1
        if score >= 40.0:
            subject_pass[sub_code] = subject_pass.get(sub_code, 0) + 1

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
            "count": count,
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
            "values": values,
        },
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

    # Again: ignore faculty scoping. Use all marks for this branch + semester.
    marks = (
        Mark.query
        .join(Student, Mark.student_id == Student.id)
        .filter(
            Student.branch == branch,
            Mark.semester == sem_i,
            Mark.year == year_i,          # ✅ use the selected exam year
        )
        .all()
    )


    # group subject scores by student
    scores_by_student: Dict[int, List[float]] = {}

    for m in marks:
        # compute / read subject score
        score = getattr(m, "subject_score", None)
        if score is None:
            try:
                comps = {
                    "mid1": m.mid1,
                    "mid2": m.mid2,
                    "internal": m.internal,
                    "end_sem": m.end_sem,
                }
                absent_map = {
                    "mid1": (m.mid1 is not None and float(m.mid1) == 0.0),
                    "mid2": (m.mid2 is not None and float(m.mid2) == 0.0),
                    "internal": (m.internal is not None and float(m.internal) == 0.0),
                    "end_sem": (m.end_sem is not None and float(m.end_sem) == 0.0),
                }
                score = compute_subject_score(comps, absent_map)
            except Exception:
                score = None

        if score is None:
            continue

        sid = m.student_id
        scores_by_student.setdefault(sid, []).append(float(score))

    counts = {"low": 0, "medium": 0, "high": 0, "unknown": 0}

    for sid, subj_scores in scores_by_student.items():
        if not subj_scores:
            counts["unknown"] += 1
            continue
        overall = round(sum(subj_scores) / len(subj_scores), 2)
        r = (map_risk(overall) or "unknown").lower()
        counts[r] = counts.get(r, 0) + 1

    total = sum(counts.values())

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
        "percentages": percentages,
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




from flask_login import current_user

@results_bp.route("/me")
@login_required
def get_current_user():
    """Return logged-in user info for SPA header (no redirect)."""
    u = current_user
    is_auth = bool(getattr(u, "is_authenticated", False))

    username = None
    role = None
    email = None

    if is_auth:
        # Try multiple possible attribute names, just in case
        username = (
            getattr(u, "username", None)
            or getattr(u, "name", None)
            or getattr(u, "user_name", None)
        )
        role = getattr(u, "role", None)
        email = getattr(u, "email", None)

    return jsonify({
        "authenticated": is_auth,
        "username": username,
        "role": role,
        "email": email,
    })
