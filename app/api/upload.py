# app/api/upload.py
import os
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from app import db
from app.models import UploadedFile

upload_bp = Blueprint("upload_api", __name__, url_prefix="/api/upload")

@upload_bp.route("", methods=["POST"])
def upload_file():
    """Handle file upload and store it on disk + DB"""
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file part"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No selected file"}), 400

        uploads_dir = current_app.config.get("UPLOAD_FOLDER") or os.path.join(
            os.path.abspath(os.path.join(current_app.root_path, "..")), "uploads"
        )
        os.makedirs(uploads_dir, exist_ok=True)

        # sanitize filename
        filename = secure_filename(file.filename)

        # 1. Create DB record first
        new_upload = UploadedFile(
            file_name=filename,
            original_file_name=filename,
            exam_type=request.form.get("exam_type"),
            uploaded_by=request.form.get("uploaded_by"),
        )
        db.session.add(new_upload)
        db.session.commit()

        # 2. Save actual file on disk, prefix with DB id
        saved_name = f"{new_upload.id}_{filename}"
        save_path = os.path.join(uploads_dir, saved_name)
        file.save(save_path)

        # 3. Update DB with real filename if needed
        new_upload.file_name = saved_name
        db.session.commit()

        return jsonify({
            "success": True,
            "id": new_upload.id,
            "file_name": saved_name,
            "saved_path": save_path
        })

    except Exception as e:
        current_app.logger.exception("upload_file failed")
        return jsonify({"error": "upload failed", "detail": str(e)}), 500
