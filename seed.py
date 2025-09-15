# seed.py  -- run from project root with venv active
from app import create_app, db
from app.models import Student, Subject, Mark
from app.utils import compute_subject_score, compute_overall_score, map_risk

def main():
    app = create_app()
    with app.app_context():
        # 1) ensure subject exists
        s = Subject.query.get('CS-401')
        if not s:
            s = Subject(sub_code='CS-401', sub_name='Maths IV', branch='CS', year=2, semester=4)
            db.session.add(s)
            db.session.commit()
            print("Inserted Subject: CS-401")
        else:
            print("Subject exists:", s.sub_name)

        # 2) ensure student exists
        st = Student.query.filter_by(pin='23189-CS-001').first()
        if not st:
            st = Student(pin='23189-CS-001', name='Student-1', branch='CS', year=2)
            db.session.add(st)
            db.session.commit()
            print("Inserted Student:", st.pin)
        else:
            print("Student exists:", st.pin)

        # 3) create or fetch mark row for student+subject+semester
        mark = Mark.query.filter_by(student_id=st.id, sub_code='CS-401', semester=4).first()
        if not mark:
            mark = Mark(student_id=st.id, sub_code='CS-401', semester=4, year=2024)
            db.session.add(mark)
            print("Created new Mark record (empty)")

        # 4) set component marks (example values)
        mark.mid1 = 15
        mark.mid2 = 18
        mark.internal = 16
        mark.end_sem = 38
        mark.attendance = 85.0
        mark.total = (mark.mid1 or 0) + (mark.mid2 or 0) + (mark.internal or 0) + (mark.end_sem or 0)

        # 5) compute subject score & risk and save
        components = {
            "attendance": mark.attendance,
            "mid1": mark.mid1,
            "mid2": mark.mid2,
            "internal": mark.internal,
            "end_sem": mark.end_sem
        }
        mark.subject_score = compute_subject_score(components)
        mark.risk = map_risk(mark.subject_score)
        db.session.commit()
        print(f"Mark saved. Subject score: {mark.subject_score} | Risk: {mark.risk} | Total: {mark.total}")

        # 6) compute and print overall for the student
        sub_scores = [m.subject_score for m in st.marks if m.subject_score is not None]
        overall = compute_overall_score(sub_scores)
        print(f"Student: {st.name} ({st.pin}) -> Overall Score: {overall} | Overall Risk: {map_risk(overall)}")

if __name__ == "__main__":
    main()
