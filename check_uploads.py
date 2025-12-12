# check_uploads.py
import os
from app import create_app, db
from app.models import UploadedFile

app = create_app()
with app.app_context():
    uploads_dir = app.config.get("UPLOAD_FOLDER") or os.path.abspath(os.path.join(app.root_path, "..", "uploads"))
    print("UPLOADS DIR:", uploads_dir)
    print("DIR EXISTS:", os.path.isdir(uploads_dir))
    try:
        print("DIR CONTENTS count:", len(os.listdir(uploads_dir)) if os.path.isdir(uploads_dir) else "n/a")
    except Exception as e:
        print("LISTDIR ERROR:", e)

    rows = UploadedFile.query.order_by(UploadedFile.id.desc()).limit(50).all()
    if not rows:
        print("No rows in uploaded_files table.")
    for f in rows:
        # probable path attempts
        candidates = []
        if f.file_name:
            candidates.append(os.path.join(uploads_dir, f.file_name))
            candidates.append(os.path.join(uploads_dir, f"{f.id}_{f.file_name}"))
        if f.original_file_name:
            candidates.append(os.path.join(uploads_dir, f.original_file_name))
            candidates.append(os.path.join(uploads_dir, f"{f.id}_{f.original_file_name}"))
        # print row + existence checks
        print("----")
        print("id:", f.id, "file_name:", f.file_name, "original:", f.original_file_name)
        for p in candidates:
            print("  ->", p, "exists:", os.path.exists(p))
        # fallback search in uploads dir for matches
        if os.path.isdir(uploads_dir):
            found = [fn for fn in os.listdir(uploads_dir) if (f.original_file_name and fn.endswith(f.original_file_name))
                     or (f.file_name and fn.endswith(f.file_name)) or fn.startswith(str(f.id))]
            print("  found in dir (fallback):", found)
