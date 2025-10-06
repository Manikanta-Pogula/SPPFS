# app/uploads.py
from flask import Blueprint, request, jsonify, render_template, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Student, Subject, Mark, UploadedFile
from app.utils.grades import compute_subject_score, compute_flags, compute_eligibility
from app.utils.excel_parser import parse_uploaded_workbook
import io
import json
from datetime import datetime

uploads_bp = Blueprint('uploads', __name__, template_folder='templates', static_folder='static')

def _mark_query_for_user():
    """
    Return base query for Mark records visible to current_user.
    Admins see all; faculty sees only their uploaded marks via uploaded_files.uploaded_by.
    """
    if current_user.is_authenticated and current_user.role == 'admin':
        return Mark.query
    # join with uploadedfile and filter by uploaded_by == current_user.id
    return Mark.query.join(UploadedFile, Mark.uploaded_file_id == UploadedFile.id).filter(UploadedFile.uploaded_by == current_user.id)

@uploads_bp.route('/data-upload')
@login_required
def data_upload_page():
    # Render page; front-end will call preview and commit APIs
    return render_template('data_upload.html')

# inside app/uploads.py - replace api_uploads_preview implementation with this one

@uploads_bp.route('/api/uploads/preview', methods=['POST'])
@login_required
def api_uploads_preview():
    """
    Improved preview:
    - Uses parse_uploaded_workbook which returns subject_cols and meta_cols
    - Builds subject name map from Subject table
    - Produces preview_rows where each subject item includes display string and parsed_components
    - Does NOT mark Rubrics/Credits as subjects (they appear under meta)
    """
    f = request.files.get('file')
    exam_type = (request.form.get('exam_type') or '').strip().lower()
    semester = int(request.form.get('semester') or 0)
    class_year = int(request.form.get('year') or 0)  # class year (1/2/3/4) - as you clarified
    file_label = request.form.get('file_label') or (f.filename if f else 'upload')

    if not f:
        return jsonify({"error": "No file uploaded"}), 400

    file_bytes = f.read()
    parsed = parse_uploaded_workbook(io.BytesIO(file_bytes), filename_hint=f.filename)
    subject_cols = parsed.get('subject_cols', [])
    meta_cols = parsed.get('meta_cols', [])
    rows = parsed.get('rows', [])

    # fetch subject names from DB for the subject codes found in file
    subjects_in_db = {}
    if subject_cols:
        db_subjects = Subject.query.filter(Subject.sub_code.in_(subject_cols)).all()
        subjects_in_db = {s.sub_code: s.sub_name for s in db_subjects}

    preview_rows = []
    parsed_count = 0

    for r in rows:
        pin = r.get('pin')
        name = r.get('name')
        attendance = r.get('attendance')
        meta = r.get('meta', {})
        row_errors = list(r.get('row_errors', []))
        subjects_preview = []

        # find student (if exists)
        student = Student.query.filter_by(pin=pin).first()
        if not student:
            # warn in preview that student not found; but we will create on commit (per your flow)
            row_errors.append(f"Student with PIN {pin} not found. Will create on commit if confirmed.")

        for s in r.get('subjects', []):
            sub_code = s.get('sub_code')
            raw_mark = s.get('raw_mark')
            absent = s.get('absent')
            parsed_components = s.get('parsed_components')
            display_text = s.get('display') or ""
            error = s.get('error')

            # subject name if known
            sub_name = subjects_in_db.get(sub_code)
            if not sub_name:
                sub_name = None  # will be shown as 'Unknown subject' on UI, per your requirement

            # build component dict for score preview (only set the parts this upload would set)
            comps = {"mid1": None, "mid2": None, "internal": None, "end_sem": None}
            absent_map = {"mid1": False, "mid2": False, "internal": False, "end_sem": False}

            if parsed_components:
                # semester breakdown present; set all components
                comps.update(parsed_components)
            else:
                if exam_type == 'mid1':
                    comps['mid1'] = raw_mark
                    absent_map['mid1'] = absent
                elif exam_type == 'mid2':
                    comps['mid2'] = raw_mark
                    absent_map['mid2'] = absent
                elif exam_type == 'semester':
                    comps['end_sem'] = raw_mark
                    absent_map['end_sem'] = absent
                else:
                    comps['internal'] = raw_mark
                    absent_map['internal'] = absent

            subject_score = compute_subject_score(comps, absent_map)
            flags = compute_flags(comps, absent_map)
            eligibility = compute_eligibility(attendance)

            # duplicate detection scoped to current user (uploader-scoped)
            duplicate_status = "none"
            existing_mark = None
            if student:
                q = Mark.query.filter_by(student_id=student.id, sub_code=sub_code, semester=semester)
                if current_user.role != 'admin':
                    q = q.join(UploadedFile, Mark.uploaded_file_id == UploadedFile.id).filter(UploadedFile.uploaded_by == current_user.id)
                existing_mark = q.first()
                if existing_mark:
                    # compare relevant components
                    identical = True
                    conflict = False
                    for comp_name, comp_val in comps.items():
                        if comp_val is None:
                            continue
                        existing_val = getattr(existing_mark, comp_name, None)
                        # treat None vs None as equal
                        try:
                            if existing_val is None and comp_val is None:
                                continue
                            if float(existing_val) != float(comp_val):
                                identical = False
                                conflict = True
                                break
                        except:
                            if existing_val != comp_val:
                                identical = False
                                conflict = True
                                break
                    duplicate_status = "identical" if identical else ("conflict" if conflict else "conflict")

            subjects_preview.append({
                "sub_code": sub_code,
                "sub_name": sub_name,   # None if unknown
                "raw_mark": raw_mark,
                "absent": absent,
                "parsed_components": parsed_components,
                "display": display_text,
                "subject_score": subject_score,
                "mid_fail": flags["mid_fail"],
                "backlog": flags["backlog"],
                "eligibility": eligibility,
                "duplicate_status": duplicate_status,
                "existing": {
                    "mid1": existing_mark.mid1 if existing_mark else None,
                    "mid2": existing_mark.mid2 if existing_mark else None,
                    "internal": existing_mark.internal if existing_mark else None,
                    "end_sem": existing_mark.end_sem if existing_mark else None,
                } if existing_mark else None,
                "error": error
            })

        if not row_errors:
            parsed_count += 1

        preview_rows.append({
            "pin": pin,
            "name": name,
            "attendance": attendance,
            "meta": meta,
            "subjects": subjects_preview,
            "row_errors": row_errors
        })

    return jsonify({
        "file_label": file_label,
        "exam_type": exam_type,
        "semester": semester,
        "class_year": class_year,
        "subject_cols": subject_cols,
        "meta_cols": meta_cols,
        "preview_rows": preview_rows,
        "status_message": f"✅ {parsed_count} records parsed for preview."
    })



@uploads_bp.route('/api/uploads/commit', methods=['POST'])
@login_required
def api_uploads_commit():
    """
    Accept JSON payload (generated from preview stage) and commit to DB.
    Expected payload:
    {
      "file_label": "...",
      "exam_type": "mid1",
      "semester": 4,
      "year": 2025,
      "rows": [
         {
           "pin": "...",
           "attendance": 85,
           "subjects": [
              {"sub_code":"CS-401","raw_mark":15,"absent":false,"action":"overwrite"|"skip"|"keep_old"}
           ]
         }, ...
      ]
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    file_label = data.get('file_label') or 'uploaded_file'
    exam_type = data.get('exam_type')
    semester = int(data.get('semester') or 0)
    year = int(data.get('year') or 0)
    rows = data.get('rows') or []

    # create UploadedFile record
    uploaded = UploadedFile(
        file_name=file_label,
        original_file_name=file_label,
        exam_type=exam_type,
        uploaded_by=current_user.id,
        uploaded_on=datetime.utcnow(),
        note=None
    )
    db.session.add(uploaded)
    db.session.flush()  # ensure uploaded.id is set

    committed = 0
    errors = []

    for r in rows:
        pin = r.get('pin')
        attendance = r.get('attendance', None)
        student = Student.query.filter_by(pin=pin).first()
        if not student:
            # create student (we assume branch present in file or later; minimal creation here)
            # Branch inference: try to pick from first subject code prefix (e.g., 'CS' from 'CS-401')
            # For simplicity create with pin,name and placeholder branch/year
            name = r.get('name') or ''
            # User selected Year in payload? If not use row-level year param
            student = Student(pin=pin, name=name, branch='UNKNOWN', exam_year=year)
            db.session.add(student)
            db.session.flush()

        for s in r.get('subjects', []):
            sub_code = s.get('sub_code')
            raw_mark = s.get('raw_mark')
            is_absent = bool(s.get('absent', False))
            action = s.get('action', 'overwrite')

            # find mark row for this student+subject+semester (regardless of uploader when committing: commit overwrites if requested)
            mark_row = Mark.query.filter_by(student_id=student.id, sub_code=sub_code, semester=semester).first()

            if mark_row and action == 'skip':
                continue

            if not mark_row:
                mark_row = Mark(student_id=student.id, sub_code=sub_code, semester=semester, year=year)
                db.session.add(mark_row)

            # update component according to exam_type or parsed_components if provided
            parsed_components = s.get('parsed_components')  # if sem breakdown provided
            if parsed_components:
                # update all four
                mark_row.mid1 = parsed_components.get('mid1')
                mark_row.mid2 = parsed_components.get('mid2')
                mark_row.internal = parsed_components.get('internal')
                mark_row.end_sem = parsed_components.get('end_sem')
            else:
                if exam_type == 'mid1':
                    mark_row.mid1 = 0.0 if is_absent else raw_mark
                elif exam_type == 'mid2':
                    mark_row.mid2 = 0.0 if is_absent else raw_mark
                elif exam_type == 'semester':
                    mark_row.end_sem = 0.0 if is_absent else raw_mark
                else:
                    mark_row.internal = 0.0 if is_absent else raw_mark

            if attendance is not None:
                mark_row.attendance = attendance

            # compute flags based on stored components
            comps = {"mid1": mark_row.mid1, "mid2": mark_row.mid2, "internal": mark_row.internal, "end_sem": mark_row.end_sem}
            absent_map = {
                "mid1": (mark_row.mid1 == 0.0 and exam_type == 'mid1' and is_absent),
                "mid2": (mark_row.mid2 == 0.0 and exam_type == 'mid2' and is_absent),
                "internal": (mark_row.internal == 0.0 and exam_type == 'internal' and is_absent),
                "end_sem": (mark_row.end_sem == 0.0 and exam_type == 'semester' and is_absent),
            }
            flags = compute_flags(comps, absent_map)
            mark_row.mid_fail = flags['mid_fail']
            mark_row.backlog = flags['backlog']
            mark_row.eligible_for_endsem = (compute_eligibility(mark_row.attendance) == 'Eligible')

            # set uploaded_file_id so visibility can be enforced
            mark_row.uploaded_file_id = uploaded.id

            mark_row.updated_on = datetime.utcnow()
            committed += 1

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Upload commit failed")
        return jsonify({"error": f"DB commit failed: {str(e)}"}), 500

    return jsonify({"committed": committed, "errors": errors, "uploaded_file_id": uploaded.id})
