# app/uploads.py
"""
Advanced uploads blueprint for SPPFS.

Responsibilities:
- /data-upload (page render)
- POST /api/uploads/preview -> parse file, validate, duplicate-detect (uploader-scoped), return preview JSON
- POST /api/uploads/commit  -> commit previewed rows to DB, handle absent vs missing, set flags, tag uploaded_file_id

Notes:
- This file expects these utility modules to exist and follow previously-discussed contracts:
    - app.utils.excel_parser.parse_uploaded_workbook(...) -> returns {subject_cols, meta_cols, rows}
    - app.utils.grades.compute_subject_score(components, absent_flags)
    - app.utils.grades.compute_flags(components, absent_flags)
    - app.utils.grades.compute_eligibility(attendance)
    - (we use a local helper normalize_for_storage below)
"""
from flask import Blueprint, request, jsonify, render_template, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Student, Subject, Mark, UploadedFile
from app.utils.excel_parser import parse_uploaded_workbook
from app.utils.grades import compute_subject_score, compute_flags, compute_eligibility
from datetime import datetime
import io
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

uploads_bp = Blueprint('uploads', __name__, template_folder='templates', static_folder='static')


# ----------------------
# Helpers
# ----------------------
def _mark_query_for_user():
    """
    Return base query for Mark records visible to current_user.
    Admin sees all; faculty sees only their uploaded marks via uploaded_files.uploaded_by.
    """
    if current_user.is_authenticated and getattr(current_user, "role", None) == 'admin':
        return Mark.query
    # join with uploaded_file and filter by uploaded_by == current_user.id
    return Mark.query.join(UploadedFile, Mark.uploaded_file_id == UploadedFile.id).filter(UploadedFile.uploaded_by == current_user.id)


def _infer_branch_from_pin(pin: str) -> Optional[str]:
    """
    Attempt to infer branch code from PIN format like: 23189-CS-001
    Returns 'CS' or None.
    """
    try:
        parts = str(pin).split('-')
        if len(parts) >= 3:
            return parts[1]
    except Exception:
        pass
    return None


def _to_float_safe(v):
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _normalize_for_storage(components: Dict[str, Optional[float]], absent_map: Dict[str, bool]) -> Dict[str, Optional[float]]:
    """
    Build storage-friendly component values:
    - If absent_map[comp] is True -> store 0.0 (explicitly absent)
    - Else if components[comp] is None -> store None (exam not held / missing)
    - Else store float value.
    Returns dict with keys mid1, mid2, internal, end_sem.
    """
    stored = {}
    for k in ("mid1", "mid2", "internal", "end_sem"):
        if absent_map.get(k):
            stored[k] = 0.0
        else:
            v = components.get(k)
            stored[k] = None if v is None else _to_float_safe(v)
    return stored


def _build_absent_map_from_payload(parsed_components: Optional[Dict[str, Any]], top_level_absent_flag: bool, exam_type: str):
    """
    Determine which components are explicit absences (True) vs missing (False).
    - If parsed_components provided: for keys present, parsed_components[key] is None -> absent True
    - Else if top_level_absent_flag True -> assume the exam component corresponding to exam_type is absent
    - Otherwise absent False
    """
    absent_map = {"mid1": False, "mid2": False, "internal": False, "end_sem": False}
    if parsed_components:
        for k in ("mid1", "mid2", "internal", "end_sem"):
            if k in parsed_components and parsed_components.get(k) is None:
                absent_map[k] = True
    else:
        # top-level absent applies only to the relevant component (mid1/mid2/internal/end_sem)
        if top_level_absent_flag:
            if exam_type == 'mid1':
                absent_map['mid1'] = True
            elif exam_type == 'mid2':
                absent_map['mid2'] = True
            elif exam_type == 'semester':
                absent_map['end_sem'] = True
            else:
                absent_map['internal'] = True
    return absent_map


# ----------------------
# Routes
# ----------------------
@uploads_bp.route('/data-upload')
@login_required
def data_upload_page():
    """Render upload page (Jinja template). UI calls preview and commit APIs."""
    return render_template('data_upload.html')


@uploads_bp.route('/api/uploads/preview', methods=['POST'])
@login_required
def api_uploads_preview():
    """
    Parse uploaded file and return preview JSON.
    Accepts multipart/form-data:
      - file: CSV/XLSX
      - exam_type: 'mid1'|'mid2'|'semester'|'internal'
      - semester: int
      - year: class year (1/2/3/4)
      - file_label: string
    Response: JSON with subject_cols, meta_cols, preview_rows (each row contains subjects array, row_errors etc.)
    """
    f = request.files.get('file')
    exam_type = (request.form.get('exam_type') or '').strip().lower()
    semester = int(request.form.get('semester') or 0)
    class_year = request.form.get('year') or None
    file_label = request.form.get('file_label') or (f.filename if f else 'upload')

    if not f:
        return jsonify({"error": "No file uploaded"}), 400

    try:
        file_bytes = f.read()
        parsed = parse_uploaded_workbook(io.BytesIO(file_bytes), filename_hint=f.filename)
    except Exception as e:
        logger.exception("Failed to parse uploaded workbook")
        return jsonify({"error": f"Failed to parse file: {str(e)}"}), 500

    subject_cols = parsed.get('subject_cols', [])
    meta_cols = parsed.get('meta_cols', [])
    rows = parsed.get('rows', [])

    # batch fetch subject names for display
    subjects_in_db = {}
    if subject_cols:
        try:
            db_subjects = Subject.query.filter(Subject.sub_code.in_(subject_cols)).all()
            subjects_in_db = {s.sub_code: s.sub_name for s in db_subjects}
        except Exception:
            subjects_in_db = {}

    preview_rows = []
    parsed_count = 0

    for r in rows:
        pin = r.get('pin') or ''
        name = r.get('name') or ''
        attendance = r.get('attendance')
        meta = r.get('meta', {})
        row_errors = list(r.get('row_errors', []))
        subjects_preview = []

        # find student (preview warns but will allow creation on commit)
        student = Student.query.filter_by(pin=pin).first()
        if not student:
            row_errors.append(f"Student with PIN {pin} not found. Will create on commit if confirmed.")

        for s in r.get('subjects', []):
            sub_code = s.get('sub_code')
            raw_mark = s.get('raw_mark')
            top_absent_flag = bool(s.get('absent', False))
            parsed_components = s.get('parsed_components')  # may be None or dict (can contain None entries)
            display = s.get('display', '')
            error = s.get('error', None)

            # subject name if present in DB (else None -> client shows 'Unknown subject (code)')
            sub_name = subjects_in_db.get(sub_code)

            # Build components dict and absent_map to compute preview subject score & flags
            comps = {"mid1": None, "mid2": None, "internal": None, "end_sem": None}
            absent_map = {"mid1": False, "mid2": False, "internal": False, "end_sem": False}

            if parsed_components:
                # parsed components available (may contain None entries which represent AB)
                for k in comps.keys():
                    if k in parsed_components:
                        comps[k] = parsed_components.get(k)
                        if parsed_components.get(k) is None:
                            absent_map[k] = True
            else:
                # single-column upload maps to one component based on exam_type
                if exam_type == 'mid1':
                    comps['mid1'] = raw_mark if raw_mark is not None and not top_absent_flag else None
                    absent_map['mid1'] = top_absent_flag
                elif exam_type == 'mid2':
                    comps['mid2'] = raw_mark if raw_mark is not None and not top_absent_flag else None
                    absent_map['mid2'] = top_absent_flag
                elif exam_type == 'semester':
                    comps['end_sem'] = raw_mark if raw_mark is not None and not top_absent_flag else None
                    absent_map['end_sem'] = top_absent_flag
                else:
                    comps['internal'] = raw_mark if raw_mark is not None and not top_absent_flag else None
                    absent_map['internal'] = top_absent_flag

            # compute preview subject score and flags using missing vs absent semantics
            subject_score = compute_subject_score(comps, absent_map)
            flags = compute_flags(comps, absent_map)
            eligibility = compute_eligibility(attendance)

            # duplicate detection (uploader-scoped unless admin)
            duplicate_status = "none"
            existing_mark = None
            if student:
                q = Mark.query.filter_by(student_id=student.id, sub_code=sub_code, semester=semester)
                if getattr(current_user, "role", None) != 'admin':
                    q = q.join(UploadedFile, Mark.uploaded_file_id == UploadedFile.id).filter(UploadedFile.uploaded_by == current_user.id)
                existing_mark = q.first()
                if existing_mark:
                    # Decide identical vs conflict: check only components being uploaded (non-None in comps and parsed_components keys)
                    identical = True
                    conflict = False
                    for comp_name, comp_val in comps.items():
                        # If component not provided in this upload, skip comparison
                        # but if parsed_components was present and comp_val is None => that's an AB we should compare as 0
                        if parsed_components is not None:
                            # parsed_components explicitly includes component (even if None)
                            check_this = True
                        else:
                            # only check the specific exam component
                            check_this = ( (exam_type == 'mid1' and comp_name == 'mid1') or
                                           (exam_type == 'mid2' and comp_name == 'mid2') or
                                           (exam_type == 'semester' and comp_name == 'end_sem') or
                                           (exam_type not in ('mid1','mid2','semester') and comp_name == 'internal') )
                        if not check_this:
                            continue
                        existing_val = getattr(existing_mark, comp_name, None)
                        # treat AB (None in parsed_components) as 0 when comparing
                        if parsed_components is not None and parsed_components.get(comp_name) is None:
                            comp_compare_val = 0.0
                        else:
                            comp_compare_val = comp_val
                        # both missing or both null -> consider equal for that component
                        if existing_val is None and comp_compare_val is None:
                            continue
                        try:
                            if (existing_val is None and comp_compare_val is not None) or (comp_compare_val is None and existing_val is not None):
                                identical = False
                                conflict = True
                                break
                            if float(existing_val) != float(comp_compare_val):
                                identical = False
                                conflict = True
                                break
                        except Exception:
                            if existing_val != comp_compare_val:
                                identical = False
                                conflict = True
                                break
                    duplicate_status = "identical" if identical else ("conflict" if conflict else "conflict")

            subjects_preview.append({
                "sub_code": sub_code,
                "sub_name": sub_name,
                "raw_mark": raw_mark,
                "absent": top_absent_flag,
                "parsed_components": parsed_components,
                "display": display,
                "subject_score": subject_score,
                "mid_fail": flags.get("mid_fail", False),
                "backlog": flags.get("backlog", False),
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
    Commit previewed rows into the DB.

    Expected JSON payload structure (from preview):
    {
      "file_label": "...",
      "exam_type": "mid1",
      "semester": 4,
      "year": 2025 (or class year),
      "rows": [
         {
           "pin": "...",
           "name": "...",
           "attendance": 85,
           "subjects": [
              {"sub_code":"CS-401","raw_mark":15,"absent":false,"parsed_components": {...} , "action":"overwrite"}
           ]
         }, ...
      ]
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    file_label = data.get('file_label') or 'uploaded_file'
    exam_type = (data.get('exam_type') or '').strip().lower()
    semester = int(data.get('semester') or 0)
    year = data.get('year') or None
    rows = data.get('rows') or []

    # create UploadedFile record
    uploaded = UploadedFile(
        file_name=file_label,
        original_file_name=file_label,
        exam_type=exam_type or 'unknown',
        uploaded_by=current_user.id,
        uploaded_on=datetime.utcnow(),
        note=None
    )
    db.session.add(uploaded)
    db.session.flush()  # to get uploaded.id

    committed = 0
    errors = []

    for r in rows:
        pin = r.get('pin')
        if not pin:
            errors.append("Row missing PIN; skipping row.")
            continue

        name = r.get('name') or ''
        attendance = r.get('attendance', None)
        # find or create student
        student = Student.query.filter_by(pin=pin).first()
        if not student:
            branch_guess = _infer_branch_from_pin(pin) or 'UNKNOWN'
            student = Student(pin=pin, name=name or 'Unknown', branch=branch_guess, exam_year=year)
            db.session.add(student)
            db.session.flush()

        for s in r.get('subjects', []):
            sub_code = s.get('sub_code')
            if not sub_code:
                errors.append(f"Missing subject code for student {pin}; skipping subject.")
                continue

            # verify subject exists in mapping table
            subj_obj = Subject.query.filter_by(sub_code=sub_code).first()
            if not subj_obj:
                # Do not fail whole commit; record error and skip this subject
                errors.append(f"Unknown subject code {sub_code} for PIN {pin}; skipped.")
                continue

            raw_mark = s.get('raw_mark')
            top_absent_flag = bool(s.get('absent', False))
            parsed_components = s.get('parsed_components')  # may be None or dict
            action = (s.get('action') or 'overwrite').lower()

            # Build original components and absent_map
            comps_orig = {"mid1": None, "mid2": None, "internal": None, "end_sem": None}
            if parsed_components:
                for k in comps_orig.keys():
                    if k in parsed_components:
                        comps_orig[k] = parsed_components.get(k)
            else:
                if exam_type == 'mid1':
                    comps_orig['mid1'] = None if top_absent_flag else raw_mark
                elif exam_type == 'mid2':
                    comps_orig['mid2'] = None if top_absent_flag else raw_mark
                elif exam_type == 'semester':
                    comps_orig['end_sem'] = None if top_absent_flag else raw_mark
                else:
                    comps_orig['internal'] = None if top_absent_flag else raw_mark

            absent_map = _build_absent_map_from_payload(parsed_components, top_absent_flag, exam_type)

            # preview score & flags using missing-vs-absent semantics
            preview_subject_score = compute_subject_score(comps_orig, absent_map)
            preview_flags = compute_flags(comps_orig, absent_map)

            # find existing mark row for this student-sub-sem (uploader-scoped detection for update decisions)
            existing_query = Mark.query.filter_by(student_id=student.id, sub_code=sub_code, semester=semester)
            existing_mark = existing_query.first()

            if existing_mark and action == 'skip':
                # skip updating this subject
                continue

            # If not present create new record
            if not existing_mark:
                mark_row = Mark(student_id=student.id, sub_code=sub_code, semester=semester, year=year)
                db.session.add(mark_row)
            else:
                mark_row = existing_mark

            # Decide per-component updates depending on action
            # If action == 'keep_old' and the stored value is not None, we keep it.
            # If action == 'overwrite', we write new values for components provided by this upload.
            # For absent components indicated in absent_map -> store 0.0
            # For components missing and not absent -> leave as NULL (None)

            # compute stored values based on action and existing values
            new_values = {}
            for comp in ("mid1", "mid2", "internal", "end_sem"):
                # Determine if this upload provides a value for this comp
                provides_value = False
                provided_val = None
                if parsed_components is not None and comp in parsed_components:
                    provides_value = True
                    provided_val = parsed_components.get(comp)  # may be None -> AB
                else:
                    # single-column uploads only "provide" the exam_type component
                    provides_value = ((exam_type == 'mid1' and comp == 'mid1') or
                                      (exam_type == 'mid2' and comp == 'mid2') or
                                      (exam_type == 'semester' and comp == 'end_sem') or
                                      (exam_type not in ('mid1','mid2','semester') and comp == 'internal'))
                    if provides_value:
                        provided_val = comps_orig.get(comp)

                # Determine target value
                if action == 'keep_old' and getattr(mark_row, comp, None) is not None:
                    # keep whatever is already stored
                    new_values[comp] = getattr(mark_row, comp)
                else:
                    # overwrite with provided value if provided; otherwise keep existing
                    if provides_value:
                        if absent_map.get(comp, False):
                            # explicit absent -> store 0.0
                            new_values[comp] = 0.0
                        else:
                            # provided_val may be None (meaning not provided) -> store None
                            new_values[comp] = None if provided_val is None else _to_float_safe(provided_val)
                    else:
                        # upload did not provide this component -> keep existing stored value as-is
                        new_values[comp] = getattr(mark_row, comp, None)

            # Apply new_values to mark_row
            mark_row.mid1 = new_values['mid1']
            mark_row.mid2 = new_values['mid2']
            mark_row.internal = new_values['internal']
            mark_row.end_sem = new_values['end_sem']

            # Recompute absent_map_now for final stored state: absent if value == 0.0 and (was flagged absent in this upload or parsed_components had None)
            absent_map_now = {
                'mid1': (parsed_components is not None and parsed_components.get('mid1') is None) or (exam_type == 'mid1' and top_absent_flag and new_values['mid1'] == 0.0),
                'mid2': (parsed_components is not None and parsed_components.get('mid2') is None) or (exam_type == 'mid2' and top_absent_flag and new_values['mid2'] == 0.0),
                'internal': (parsed_components is not None and parsed_components.get('internal') is None) or (exam_type not in ('mid1','mid2','semester') and top_absent_flag and new_values['internal'] == 0.0),
                'end_sem': (parsed_components is not None and parsed_components.get('end_sem') is None) or (exam_type == 'semester' and top_absent_flag and new_values['end_sem'] == 0.0)
            }

            # Compute flags on final stored numbers; compute_flags expects comps dict + absent_map
            comps_for_flags = {
                'mid1': new_values['mid1'],
                'mid2': new_values['mid2'],
                'internal': new_values['internal'],
                'end_sem': new_values['end_sem']
            }
            flags_final = compute_flags(comps_for_flags, absent_map_now)

            # store flags & derived fields
            try:
                mark_row.mid_fail = bool(flags_final.get('mid_fail', False))
            except Exception:
                pass
            try:
                mark_row.backlog = bool(flags_final.get('backlog', False))
            except Exception:
                pass

            # store attendance/eligibility
            try:
                if attendance is not None:
                    mark_row.attendance = _to_float_safe(attendance)
                mark_row.eligible_for_endsem = (compute_eligibility(mark_row.attendance) == 'Eligible')
            except Exception:
                mark_row.eligible_for_endsem = None

            # Optionally store subject_score if model has column (best-effort)
            try:
                # compute subject score according to upload's intended interpretation (use absent_map_now)
                computed_score = compute_subject_score(comps_for_flags, absent_map_now)
                mark_row.subject_score = computed_score
            except Exception:
                # ignore if column not present
                pass

            # Tag with uploaded_file_id and timestamp
            mark_row.uploaded_file_id = uploaded.id
            mark_row.updated_on = datetime.utcnow()

            committed += 1

    # commit transaction
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.exception("Upload commit failed")
        return jsonify({"error": f"DB commit failed: {str(e)}"}), 500

    return jsonify({"committed": committed, "errors": errors, "uploaded_file_id": uploaded.id})
