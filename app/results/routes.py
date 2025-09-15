# app/results/routes.py
import re
from flask import Blueprint, request, jsonify, current_app, send_file
from io import StringIO
import csv

from app import db
from app.models import Student, Mark, Subject
from app.utils import compute_subject_score, compute_overall_score, map_risk, generate_feedback

results_bp = Blueprint("results", __name__, url_prefix="/api/results")

# PIN validation - flexible but rejects tiny/garbage pins like "189" or empty.
PIN_REGEX = re.compile(r'^\s*\d{2,}-[A-Za-z0-9]+-\d+\s*$', re.IGNORECASE)

def _is_pin_valid(pin: str) -> bool:
    if not pin:
        return False
    p = str(pin).strip()
    if PIN_REGEX.match(p):
        return True
    # fallback: require at least 7 chars and a dash (e.g. 23189-CS-001)
    if len(p) >= 7 and '-' in p and any(ch.isdigit() for ch in p):
        return True
    return False

# compute subject details & per-student overall for a semester
def _compute_student_score_for_sem(student, semester):
    marks = Mark.query.filter_by(student_id=student.id, semester=semester).all()
    details = []
    scores = []
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
            "risk": m.risk
        })
    overall = None
    if scores:
        overall = compute_overall_score(scores)
    return overall, len(details), details

# -------------------------
# 1) Search / listing endpoint
# -------------------------
@results_bp.route("/search")
def search_student():
    pin = (request.args.get("pin") or "").strip()
    q = (request.args.get("q") or "").strip()
    branch = (request.args.get("branch") or "").strip()
    exam_year = request.args.get("year")
    semester = request.args.get("semester")

    # single-student (by pin) -> return student + marks
    if pin:
        student = Student.query.filter_by(pin=pin).first()
        if not student:
            return jsonify({"error": "Student not found"}), 404

        sem = int(semester) if semester and semester.isdigit() else None
        if sem is None:
            # return marks grouped by semester
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

        # extract risk subjects (marks < 40 OR subject_score < 40)
        risk_subjects = [d["sub_name"] for d in details if d.get("subject_score") and d["subject_score"] < 40]

        # average attendance if available
        atts = [d.get("attendance") for d in details if d.get("attendance") is not None]
        avg_attendance = (sum(atts) / len(atts)) if atts else None

        # generate feedback
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
    sort = (request.args.get("sort") or "pin").lower()      # pin | name | risk | class_avg | attendance
    order = (request.args.get("order") or "asc").lower()

    query = Student.query
    if branch:
        query = query.filter_by(branch=branch)
    if exam_year and exam_year.isdigit():
        query = query.filter_by(exam_year=int(exam_year))

    if q:
        qlike = f"%{q}%"
        query = query.filter(db.or_(Student.pin.ilike(qlike), Student.name.ilike(qlike)))

    pagination = query.order_by(Student.pin).paginate(page=page, per_page=per_page, error_out=False)

    items = []
    batch_scores = []
    sem = int(semester) if semester and semester.isdigit() else None

    # Build rows, but filter out obviously-bad records (college header rows, tiny pins)
    temp_rows = []
    for s in pagination.items:
        # Skip obviously invalid pins and rows which look like college header
        if not _is_pin_valid(s.pin):
            continue
        if s.name and 'polytechnic' in s.name.lower():
            # treat college name separately, skip in student rows
            continue

        overall = None
        subj_count = 0
        attendance_val = None
        if sem is not None:
            overall, subj_count, details = _compute_student_score_for_sem(s, sem)
            # compute mean attendance for that student (across their subject rows where attendance present)
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

    # Sorting
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
# 2) Batch overview (20% panel)
# -------------------------
@results_bp.route("/overview")
def batch_overview():
    branch = (request.args.get("branch") or "").strip()
    exam_year = request.args.get("year")
    semester = request.args.get("semester")

    if not branch or not exam_year or not semester:
        return jsonify({"error": "branch, year and semester required"}), 400

    year_i = int(exam_year)
    sem_i = int(semester)

    students = Student.query.filter_by(branch=branch, exam_year=year_i).all()
    total_students = len(students)
    risk_counts = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
    attendance_vals = []
    overall_vals = []

    for s in students:
        # ignore college header rows or invalid pins if they exist in the table
        if not _is_pin_valid(s.pin):
            continue

        overall, _, details = _compute_student_score_for_sem(s, sem_i)
        if overall is None:
            risk_counts["unknown"] += 1
        else:
            r = map_risk(overall)
            risk_counts[(r or "unknown")] = risk_counts.get((r or "unknown"), 0) + 1
            overall_vals.append(overall)
        atts = [d.get("attendance") for d in details if d.get("attendance") is not None]
        if atts:
            attendance_vals.append(sum(atts) / len(atts))

    avg_attendance = (sum(attendance_vals) / len(attendance_vals)) if attendance_vals else None
    avg_class_perf = (sum(overall_vals) / len(overall_vals)) if overall_vals else None

    return jsonify({
        "total_students": total_students,
        "risk_counts": risk_counts,
        "avg_attendance": avg_attendance,
        "avg_class_performance": avg_class_perf
    })


# -------------------------
# 3) Export CSV (simple)
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
        overall = None
        overall_att = None
        if sem_i:
            overall, _, details = _compute_student_score_for_sem(s, sem_i)
            atts = [d.get("attendance") for d in details if d.get("attendance") is not None]
            if atts:
                overall_att = sum(atts) / len(atts)
        risk = map_risk(overall) if overall is not None else ""
        writer.writerow([s.pin, s.name, s.branch, s.exam_year, overall_att or "", overall or "", risk or ""])

    out.seek(0)
    return send_file(
        StringIO(out.getvalue()),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"students_export_{branch}_{exam_year}_{semester}.csv"
    )

@results_bp.route("/institution")
def get_institution():
    from app.models import Institution
    inst = Institution.query.first()
    if not inst:
        return jsonify({"name": ""})
    return jsonify({"name": inst.name})


# -------------------------
# Graph endpoints (append to app/results/routes.py)
# -------------------------
from flask import request, jsonify
from collections import defaultdict

# @results_bp.route("/graphs/subject_averages")
# def subject_averages_graph():
#     """
#     GET /api/results/graphs/subject_averages?branch=CS&year=2024&semester=4
#     Returns per-subject average (%) across students in the batch.
#     """
#     branch = (request.args.get("branch") or "").strip()
#     year = request.args.get("year")
#     semester = request.args.get("semester")

#     if not branch or not semester:
#         return jsonify({"error": "branch and semester are required"}), 400

#     try:
#         sem_i = int(semester)
#     except:
#         return jsonify({"error": "semester must be an integer"}), 400

#     # optional year filter (if provided)
#     year_i = int(year) if year and year.isdigit() else None

#     # get subjects for that branch+semester (and optionally year)
#     q = Subject.query.filter_by(branch=branch, semester=sem_i)
#     if year_i:
#         q = q.filter_by(year=year_i)
#     subjects = q.order_by(Subject.sub_code).all()

#     out = []
#     labels = []
#     values = []
#     counts = []

#     for subj in subjects:
#         # use exact sub_code stored in DB (subject.sub_code)
#         marks_query = Mark.query.join(Student, Mark.student_id == Student.id).filter(
#             Mark.sub_code == subj.sub_code,
#             Mark.semester == sem_i,
#             Student.branch == branch
#         )
#         if year_i:
#             marks_query = marks_query.filter(Student.year == year_i)

#         marks = marks_query.all()

#         scores = []
#         for m in marks:
#             ss = m.subject_score
#             if ss is None:
#                 # attempt to compute from components (not expensive for moderate datasets)
#                 try:
#                     comps = {'attendance': m.attendance, 'mid1': m.mid1, 'mid2': m.mid2, 'internal': m.internal, 'end_sem': m.end_sem}
#                     ss = compute_subject_score(comps)
#                 except Exception:
#                     ss = None
#             if ss is not None:
#                 scores.append(float(ss))

#         avg = round(sum(scores) / len(scores), 2) if scores else None
#         out.append({
#             "sub_code": subj.sub_code,
#             "sub_name": subj.sub_name or "",
#             "average": avg,           # 0-100 scale
#             "count_students": len(scores)
#         })
#         labels.append(subj.sub_code)
#         values.append(avg if avg is not None else 0)
#         counts.append(len(scores))

#     return jsonify({
#         "branch": branch,
#         "year": year_i,
#         "semester": sem_i,
#         "subjects": out,
#         "labels": labels,   # for chart x-axis
#         "values": values,   # for chart y-axis (averages as numbers)
#         "counts": counts
#     }), 200   


@results_bp.route("/graphs/risk_distribution")
def risk_distribution_graph():
    """
    GET /api/results/graphs/risk_distribution?branch=CS&year=2024&semester=4
    Returns counts & percentages for Low/Medium/High/Unknown risk categories in the batch.
    """
    branch = (request.args.get("branch") or "").strip()
    year = request.args.get("year")
    semester = request.args.get("semester")

    if not branch or not semester:
        return jsonify({"error": "branch and semester are required"}), 400

    try:
        sem_i = int(semester)
    except:
        return jsonify({"error": "semester must be an integer"}), 400

    year_i = int(year) if year and year.isdigit() else None

    students_q = Student.query.filter_by(branch=branch)
    if year_i:
        students_q = students_q.filter_by(year=year_i)
    students = students_q.all()

    counts = defaultdict(int)
    total_considered = 0

    for s in students:
        # compute overall for this semester using existing helper
        overall, _, _ = _compute_student_score_for_sem(s, sem_i)
        if overall is None:
            counts["unknown"] += 1
        else:
            r = map_risk(overall) or "unknown"
            # ensure normalized keys
            r_key = r.lower()
            if r_key not in ("low", "medium", "high"):
                r_key = "unknown"
            counts[r_key] += 1
        total_considered += 1

    # compute percentages
    pct = {}
    for k in ("low", "medium", "high", "unknown"):
        c = counts.get(k, 0)
        pct[k] = round((c / total_considered * 100), 2) if total_considered else 0.0

    return jsonify({
        "branch": branch,
        "year": year_i,
        "semester": sem_i,
        "total_students": total_considered,
        "counts": {k: counts.get(k, 0) for k in ("low", "medium", "high", "unknown")},
        "percentages": pct
    }), 200



# -------------------------
# 4) Graph & Analytics Endpoints
# -------------------------
@results_bp.route("/graphs/subject_averages")
def subject_averages_graph():
    branch = (request.args.get("branch") or "").strip()
    year = request.args.get("year")
    semester = request.args.get("semester")

    if not branch or not year or not semester:
        return jsonify({"error": "branch, year, semester required"}), 400

    try:
        year_i = int(year)
        sem_i = int(semester)
    except ValueError:
        return jsonify({"error": "year and semester must be integers"}), 400

    # ✅ FIX: use exam_year (not year)
    students = Student.query.filter_by(branch=branch, exam_year=year_i).all()

    subject_totals = {}
    subject_counts = {}

    for s in students:
        marks = Mark.query.filter_by(student_id=s.id, semester=sem_i).all()
        for m in marks:
            if m.total is not None:
                subject_totals[m.sub_code] = subject_totals.get(m.sub_code, 0) + m.total
                subject_counts[m.sub_code] = subject_counts.get(m.sub_code, 0) + 1

    subject_avgs = []
    for sub_code, total in subject_totals.items():
        avg = total / subject_counts[sub_code]
        subj = Subject.query.filter_by(sub_code=sub_code).first()
        subject_avgs.append({
            "sub_code": sub_code,
            "sub_name": subj.sub_name if subj else sub_code,
            "average": avg
        })

    return jsonify({"items": subject_avgs})
