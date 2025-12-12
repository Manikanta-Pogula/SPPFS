# scripts/update_marks_from_components.py
"""
Run with: FLASK_APP=app:create_app flask shell
Then in shell: exec(open("scripts/update_marks_from_components.py").read())
Or: python -m flask run this file (see instructions below)
"""

from app import create_app, db
from app.models import Mark, Subject, Student
from app.utils import grades as grades_utils  # uses compute_subject_score, compute_flags
from app.results.routes import map_risk  # or re-implement map_risk here

app = create_app()
with app.app_context():
    BATCH = 500
    q = Mark.query.order_by(Mark.id)
    total = q.count()
    print(f"Marks total: {total}")
    updated = 0
    i = 0
    for m in q.yield_per(BATCH):
        i += 1
        comps = {
            "mid1": m.mid1,
            "mid2": m.mid2,
            "internal": m.internal,
            "end_sem": m.end_sem,
        }
        # derive absent flags: your app considers explicit 0.0 as absent
        absent_flags = {
            "mid1": (m.mid1 is not None and float(m.mid1) == 0.0),
            "mid2": (m.mid2 is not None and float(m.mid2) == 0.0),
            "internal": (m.internal is not None and float(m.internal) == 0.0),
            "end_sem": (m.end_sem is not None and float(m.end_sem) == 0.0),
        }
        try:
            ss = grades_utils.compute_subject_score(comps, absent_flags)
        except Exception:
            # fallback to simple percent if above fails
            try:
                ss = grades_utils.compute_subject_score(comps)
            except Exception:
                ss = None

        # compute flags
        try:
            flags = grades_utils.compute_flags(comps, absent_flags)
        except Exception:
            flags = {"mid_fail": False, "backlog": False}

        # write only when meaningful
        if ss is not None:
            m.subject_score = float(ss)
            m.risk = map_risk(m.subject_score) if m.subject_score is not None else None
            m.mid_fail = bool(flags.get("mid_fail", False))
            m.backlog = bool(flags.get("backlog", False))
            updated += 1

        if i % 500 == 0:
            db.session.commit()
            print(f"Processed {i} rows, updated {updated}")

    db.session.commit()
    print(f"Done. Total updated: {updated}")
