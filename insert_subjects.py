# insert_subjects.py

from app import create_app, db
from app.models import Subject

# Create app context (so DB is available)
app = create_app()
ctx = app.app_context()
ctx.push()

# Subjects to insert (add/update here if needed)
subs = [
    ("SC-401", "Mathematics-IV"),
    ("CS-402", "Computer Networks"),
    ("CS-403", "Operating Systems"),
    ("CS-404", "Database Management Systems"),
    ("CS-405", "Software Engineering"),
    ("CS-406", "Theory of Computation"),
    ("CS-407", "Compiler Design"),
    ("CS-408", "Artificial Intelligence"),
    ("CS-409", "Web Technologies"),
    ("HU-410", "Professional Communication")
]

# Insert only if not already in DB
for code, name in subs:
    existing = Subject.query.filter_by(sub_code=code).first()
    if not existing:
        subj = Subject(
            sub_code=code,
            sub_name=name,
            semester=4,
            branch="CS",
            year=2024
        )
        db.session.add(subj)
        print(f"Inserted subject: {code} - {name}")
    else:
        print(f"Skipped (already exists): {code}")

db.session.commit()
print("✅ Subjects inserted/updated successfully.")
