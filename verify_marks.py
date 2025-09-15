# verify_marks.py
from app import create_app
from app.models import Subject, Mark, Student
app = create_app()
with app.app_context():
    print("Total subjects:", Subject.query.count())
    print("Sample subjects:", [s.sub_code for s in Subject.query.limit(10).all()])
    print("Total marks rows:", Mark.query.count())
    print("Sample mark rows (5):")
    for m in Mark.query.limit(5).all():
        print(m.id, m.student_id, m.sub_code, m.mid1, m.mid2, m.internal, m.end_sem, m.attendance, m.subject_score, m.risk)
