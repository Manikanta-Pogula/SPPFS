# app/main/routes.py

from flask import Blueprint, render_template, jsonify
from app.models import db  # Import your database and models here when needed

# -----------------------------
# Blueprint Setup
# -----------------------------
main_bp = Blueprint("main", __name__)

# -----------------------------
# Web Pages
# -----------------------------

@main_bp.route("/")
def index():
    """Homepage route."""
    return render_template("index.html")


@main_bp.route("/dashboard")
def dashboard():
    """Faculty dashboard route."""
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
# API Routes
# -----------------------------

@main_bp.route("/api/graph-analysis")
def graph_analysis():
    """
    API endpoint for Graph Analysis.
    Currently returns dummy data.
    Later: Replace with real SQLAlchemy queries from Student, Mark, Subject tables.
    """
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
    """
    UI preview page — opens in new tab and fetches JSON from
    /api/files/<file_id>/preview to display a friendly table.
    """
    return render_template("file_view.html", file_id=file_id)