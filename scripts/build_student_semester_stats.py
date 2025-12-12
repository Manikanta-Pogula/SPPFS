# scripts/build_student_semester_stats.py
from app import create_app, db
from app.models import Student, Mark, StudentSemesterStat
from app.utils.grades import compute_subject_score, compute_overall_score
from app.results.routes import map_risk
from datetime import datetime

app = create_app()
with app.app_context():
    students = Student.query.all()
    print("Students:", len(students))
    updated = 0
    for st in students:
        sems = sorted({m.semester for m in Mark.query.filter_by(student_id=st.id).all()})
        for sem in sems:
            marks = Mark.query.filter_by(student_id=st.id, semester=sem).all()
            scores = []
            for m in marks:
                comps = {
                    "mid1": m.mid1,
                    "mid2": m.mid2,
                    "internal": m.internal,
                    "end_sem": m.end_sem,
                }
                absent_map = {
                    "mid1": (m.mid1 is not None and float(m.mid1) == 0.0),
                    "mid2": (m.mid2 is not None and float(m.mid2) == 0.0),
                    "internal": (m.internal is not None and float(m.internal) == 0.0),
                    "end_sem": (m.end_sem is not None and float(m.end_sem) == 0.0),
                }
                try:
                    ss = compute_subject_score(comps, absent_map)
                except TypeError:
                    ss = compute_subject_score(comps)
                except Exception:
                    ss = None
                if ss is not None:
                    scores.append(float(ss))
            try:
                overall = compute_overall_score(scores) if scores else None
            except Exception:
                overall = round(sum(scores) / len(scores), 2) if scores else None
            risk = map_risk(overall) if overall is not None else None

            stat = StudentSemesterStat.query.filter_by(student_id=st.id, semester=sem).first()
            if stat:
                stat.overall_score = overall
                stat.risk = risk
                stat.exam_year = st.exam_year
                stat.computed_on = datetime.utcnow()
            else:
                stat = StudentSemesterStat(student_id=st.id, semester=sem, exam_year=st.exam_year,
                                           overall_score=overall, risk=risk, computed_on=datetime.utcnow())
                db.session.add(stat)
            updated += 1
    db.session.commit()
    print("Backfill finished. Stats created/updated:", updated)
