from flask import Blueprint, jsonify, request, send_file
from app import db
from app.models import UploadedFile
import os

files_bp = Blueprint("files", __name__, url_prefix="/api/files")

# List all uploaded files
@files_bp.route("", methods=["GET"])
def list_files():
    q = (request.args.get("q") or "").strip()
    exam_type = (request.args.get("exam_type") or "").strip()
    query = UploadedFile.query

    if q:
        like = f"%{q}%"
        query = query.filter(UploadedFile.file_name.ilike(like))

    if exam_type:
        query = query.filter_by(exam_type=exam_type)

    files = query.order_by(UploadedFile.id.desc()).all()
    items = []
    for f in files:
        items.append({
            "id": f.id,
            "file_name": f.file_name,
            "original_file_name": f.original_file_name,
            "exam_type": f.exam_type,
            "uploaded_on": f.uploaded_on.isoformat() if f.uploaded_on else None
        })

    return jsonify({"total": len(items), "items": items})


# Download file by ID
@files_bp.route("/<int:file_id>/download", methods=["GET"])
def download_file(file_id):
    f = UploadedFile.query.get(file_id)
    if not f:
        return jsonify({"error": "File not found"}), 404

    file_path = f.file_path
    if not os.path.exists(file_path):
        return jsonify({"error": "File missing on disk"}), 404

    return send_file(file_path, as_attachment=True, download_name=f.original_file_name)

# --- append to app/files/routes.py ---

from flask import render_template   # add to top of file if not already imported

@files_bp.route('/<int:file_id>/view')
def file_view(file_id):
    """
    Render a lightweight HTML preview page. The page's JS will fetch the
    existing API endpoint /api/files/<id>/preview and render a table.
    This keeps parsing logic in the API and avoids duplicating code.
    """
    return render_template('file_preview.html', file_id=file_id)
