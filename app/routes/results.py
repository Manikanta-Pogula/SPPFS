# app/routes/results.py

from flask import Blueprint, jsonify
from app import db
from app.models import Student, Mark, Subject
from app.utils.feedback import generate_feedback

results_bp = Blueprint("results", __name__, url_prefix="/results")

@results_bp.route("/student/<string:pin>/results", methods=["GET"])
def get_student_results(pin):
    student = Student.query.filter_by(pin=pin).first()

    if not student:
        return jsonify({"error": "Student not found"}), 404

    # Group marks by semester
    semesters = {}
    marks = Mark.query.filter_by(student_id=student.id).all()

    for mark in marks:
        sem = mark.semester
        if sem not in semesters:
            semesters[sem] = {
                "semester": sem,
                "subjects": [],
                "sgpa": 0,
                "feedback": ""
            }

        subject = Subject.query.get(mark.subject_id)
        semesters[sem]["subjects"].append({
            "subject_code": subject.code,
            "subject_name": subject.name,
            "marks": mark.marks_obtained,
            "max_marks": subject.max_marks
        })

    # Calculate SGPA + feedback for each semester
    for sem, data in semesters.items():
        total_marks = sum([s["marks"] for s in data["subjects"]])
        total_max = sum([s["max_marks"] for s in data["subjects"]])
        sgpa = round((total_marks / total_max) * 10, 2) if total_max > 0 else 0
        data["sgpa"] = sgpa
        data["feedback"] = generate_feedback(sgpa, data["subjects"])

    response = {
        "pin": student.pin,
        "name": student.name,
        "institution": student.institution.name if student.institution else None,
        "results": list(semesters.values())
    }

    return jsonify(response), 200
