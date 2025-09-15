# app/main/routes.py
from flask import Blueprint, render_template, request, redirect, url_for

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    # homepage
    return render_template('index.html')

@main_bp.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@main_bp.route('/uploaded-files')
def uploaded_files_page():
    return render_template('uploaded_files.html')

@main_bp.route('/student-results')
def student_results_page():
    return render_template('student_results.html')
