# app/api/files.py
import os
import csv
import traceback
from flask import Blueprint, request, jsonify, current_app, send_file
from app.models import UploadedFile, db

# optional Excel preview dependency
try:
    import openpyxl
    HAVE_OPENPYXL = True
except Exception:
    HAVE_OPENPYXL = False

files_bp = Blueprint("files_api", __name__, url_prefix="/api/files")


def get_uploads_dir():
    """Return absolute path to uploads directory (configurable via UPLOAD_FOLDER)."""
    cfg = current_app.config.get("UPLOAD_FOLDER")
    if cfg:
        return os.path.abspath(cfg)
    # fallback: project_root/uploads
    project_root = os.path.abspath(os.path.join(current_app.root_path, ".."))
    return os.path.join(project_root, "uploads")


def find_file_on_disk(uploaded: UploadedFile):
    """
    Try multiple heuristics to find the physical file:
    - original_file_name
    - file_name
    - "<id>_original_file_name"
    - "<id>_file_name"
    - fallback: any file in uploads dir that endswith original_file_name or startswith id
    """
    uploads_dir = get_uploads_dir()
    if not os.path.isdir(uploads_dir):
        return None

    candidates = []
    if uploaded.original_file_name:
        candidates.append(uploaded.original_file_name)
    if uploaded.file_name:
        candidates.append(uploaded.file_name)
    if uploaded.original_file_name:
        candidates.append(f"{uploaded.id}_{uploaded.original_file_name}")
    if uploaded.file_name:
        candidates.append(f"{uploaded.id}_{uploaded.file_name}")
    candidates = [c for c in candidates if c]

    # check exact names
    for cand in candidates:
        p = os.path.join(uploads_dir, cand)
        if os.path.exists(p):
            return p

    # fallback: search directory
    try:
        for fname in os.listdir(uploads_dir):
            for cand in candidates:
                if fname == cand or fname.endswith(cand) or fname.startswith(str(uploaded.id)):
                    p = os.path.join(uploads_dir, fname)
                    if os.path.exists(p):
                        return p
    except Exception:
        current_app.logger.exception("Error listing uploads dir")

    return None


@files_bp.route("", methods=["GET"])
def list_files():
    """List uploaded files. query params: q (search), exam_type"""
    try:
        q = (request.args.get("q") or "").strip()
        et = (request.args.get("exam_type") or "").strip()

        query = UploadedFile.query
        if et:
            query = query.filter_by(exam_type=et)
        if q:
            like = f"%{q}%"
            query = query.filter(
                db.or_(
                    UploadedFile.file_name.ilike(like),
                    UploadedFile.original_file_name.ilike(like)
                )
            )
        items = []
        for f in query.order_by(UploadedFile.uploaded_on.desc()).all():
            items.append({
                "id": f.id,
                "file_name": f.file_name,
                "original_file_name": f.original_file_name,
                "exam_type": f.exam_type,
                "uploaded_on": f.uploaded_on.isoformat() if f.uploaded_on else None,
                "uploaded_by": f.uploaded_by
            })
        return jsonify({"total": len(items), "items": items})
    except Exception as e:
        current_app.logger.exception("list_files error")
        return jsonify({"error": "internal error", "detail": str(e)}), 500


@files_bp.route("/<int:file_id>/preview", methods=["GET"])
def preview_file(file_id):
    """
    Preview file: returns { meta, columns, sample_rows } (best-effort).
    Supports CSV natively, XLSX/XLS if openpyxl available.
    """
    f = UploadedFile.query.get(file_id)
    if not f:
        return jsonify({"error": "file not found"}), 404

    path = find_file_on_disk(f)
    if not path:
        return jsonify({"error": "file not found on disk", "checked_dir": get_uploads_dir()}), 404

    ext = os.path.splitext(path)[1].lower()
    meta = {
        "file_name": f.file_name,
        "original_file_name": f.original_file_name,
        "exam_type": f.exam_type,
        "uploaded_on": f.uploaded_on.isoformat() if f.uploaded_on else None,
        "size": os.path.getsize(path)
    }

    try:
        if ext == ".csv":
            with open(path, newline="", encoding="utf-8", errors="replace") as fh:
                # sniff (best-effort)
                sample = fh.read(4096)
                fh.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample) if sample else csv.excel
                except Exception:
                    dialect = csv.excel
                reader = csv.reader(fh, dialect)
                rows = []
                for i, row in enumerate(reader):
                    rows.append(row)
                    if i >= 10:
                        break
                columns = rows[0] if rows else []
                sample_rows = rows[1:6] if len(rows) > 1 else []
            return jsonify({"meta": meta, "columns": columns, "sample_rows": sample_rows})

        elif ext in (".xls", ".xlsx"):
            if not HAVE_OPENPYXL:
                return jsonify({"meta": meta, "error": "Excel preview requires 'openpyxl' package. Install with: pip install openpyxl"}), 200
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            ws = wb.active
            rows = []
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                rows.append([("" if v is None else str(v)) for v in row])
                if i >= 10:
                    break
            columns = rows[0] if rows else []
            sample_rows = rows[1:6] if len(rows) > 1 else []
            return jsonify({"meta": meta, "columns": columns, "sample_rows": sample_rows})

        else:
            # unsupported type — return meta only
            return jsonify({"meta": meta, "error": f"Preview not supported for '{ext}'"}), 200

    except Exception as e:
        current_app.logger.exception("preview failed")
        return jsonify({"meta": meta, "error": "preview failed", "detail": str(e)}), 500


@files_bp.route("/<int:file_id>/download", methods=["GET"])
def download_file(file_id):
    f = UploadedFile.query.get(file_id)
    if not f:
        return jsonify({"error": "not found"}), 404

    path = find_file_on_disk(f)
    if not path:
        return jsonify({"error": "file not found on disk"}), 404

    try:
        return send_file(path, as_attachment=True, download_name=(f.original_file_name or f.file_name))
    except Exception as e:
        current_app.logger.exception("download failed")
        return jsonify({"error": "download failed", "detail": str(e)}), 500


@files_bp.route("/<int:file_id>", methods=["DELETE"])
def delete_file(file_id):
    f = UploadedFile.query.get(file_id)
    if not f:
        return jsonify({"error": "not found"}), 404

    remove_file = str(request.args.get("remove_file", "false")).lower() in ("1", "true", "yes")
    try:
        if remove_file:
            path = find_file_on_disk(f)
            if path and os.path.exists(path):
                os.remove(path)
        db.session.delete(f)
        db.session.commit()
        return jsonify({"success": True, "deleted_id": file_id})
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("delete failed")
        return jsonify({"error": "delete failed", "detail": str(e)}), 500


from flask import render_template

@files_bp.route("/<int:file_id>/view", methods=["GET"])
def view_file(file_id):
    """Render a full-page table preview for an uploaded file."""
    f = UploadedFile.query.get(file_id)
    if not f:
        return "File not found", 404

    path = find_file_on_disk(f)
    if not path:
        return f"File not found on disk ({get_uploads_dir()})", 404

    ext = os.path.splitext(path)[1].lower()
    rows = []
    try:
        if ext == ".csv":
            with open(path, newline="", encoding="utf-8", errors="replace") as fh:
                reader = csv.reader(fh)
                for i, row in enumerate(reader):
                    rows.append([("" if v is None else str(v)) for v in row])
                    if i > 50:  # limit for preview
                        break
        elif ext in (".xls", ".xlsx"):
            if not HAVE_OPENPYXL:
                return "Excel preview requires openpyxl. Install with: pip install openpyxl", 500
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            ws = wb.active
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                rows.append([("" if v is None else str(v)) for v in row])
                if i > 50:
                    break
        else:
            return f"Preview not supported for {ext}", 400
    except Exception as e:
        current_app.logger.exception("view_file failed")
        return f"Error parsing file: {e}", 500

    if not rows:
        return "No data in file", 200

    columns = rows[0]
    sample_rows = rows[1:]

    return render_template(
        "file_view.html",
        file=f,
        columns=columns,
        rows=sample_rows
    )
