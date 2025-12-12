# app/main/routes.py

from flask import Blueprint, render_template, jsonify, current_app, send_from_directory
from jinja2 import TemplateNotFound
import os

main_bp = Blueprint("main", __name__)

# -----------------------------
# Home (server-rendered)
# -----------------------------
@main_bp.route("/")
def home():
    """
    Render the server-side Home page at "/".
    Falls back to index.html if home.html is not present.
    """
    try:
        return render_template("home.html")
    except TemplateNotFound:
        # Safe fallback in case you haven't created home.html yet
        return render_template("index.html")


# -----------------------------
# SPA entry (serve built React app)
# NOTE: We no longer claim "/" here; this prevents the SPA
# from taking over the root path.
# -----------------------------
@main_bp.route("/<path:path>")
def spa(path):
    """
    Serve the Single Page Application built files (from static/spa).
    If a static file exists (js/css), serve it. Otherwise render spa_index.html
    so the client-side router can handle the path.
    """
    static_spa_folder = os.path.join(current_app.root_path, "static", "spa")

    # If path is a file that exists in static/spa, send it directly:
    if path and os.path.exists(os.path.join(static_spa_folder, path)):
        return send_from_directory(static_spa_folder, path)

    # Otherwise, render the SPA template entry (index)
    return render_template("spa_index.html")


# -----------------------------
# Existing UI pages (kept for compatibility)
# -----------------------------
@main_bp.route("/dashboard")
def dashboard():
    """Faculty dashboard route (kept for compatibility)."""
    return render_template("dashboard.html")


@main_bp.route("/uploaded-files")
def uploaded_files_page():
    """Uploaded files page."""
    return render_template("uploaded_files.html")


@main_bp.route("/student-results")
def student_results_page():
    """Student results page."""
    return render_template("student_results.html")


# -----------------------------
# API Routes (dummy example)
# -----------------------------
@main_bp.route("/api/graph-analysis")
def graph_analysis():
    # This is a simple example; your real API endpoints are elsewhere
    response = {
        "subjects": [
            {"name": "Theory of Computation", "code": "CS-406", "avg": 90, "pass": "100%", "students": 120},
            {"name": "Web Technologies", "code": "CS-409", "avg": 85, "pass": "96%", "students": 115},
            {"name": "Operating Systems", "code": "CS-403", "avg": 72, "pass": "88%", "students": 110},
        ],
        "risk": {
            "High": 10,
            "Medium": 30,
            "Low": 50,
            "Unknown": 5
        }
    }
    return jsonify(response)


@main_bp.route("/files/<int:file_id>/view")
def file_view_page(file_id):
    return render_template("file_view.html", file_id=file_id)
