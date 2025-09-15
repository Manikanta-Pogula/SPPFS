# create_subjects_from_preview.py
import json, re
from app import create_app, db
from app.models import Subject

# CONFIG: change if needed
PREVIEW_FILE = "preview.json"
DEFAULT_BRANCH = "CS"          # change if needed
DEFAULT_SEMESTER = 4           # change if needed (use the same semester you uploaded)
DEFAULT_YEAR = (DEFAULT_SEMESTER + 1) // 2  # map semester -> year (1..3)

IGNORED_PATTERNS = [r'^\s*rubrics', r'^\s*total\s*$', r'^\s*credits', r'^\s*total grade', r'^\s*sgpa', r'^\s*cgpa', r'^\s*result', r'^\s*grade', r'^\s*remark']

def is_ignored(col):
    lc = str(col).lower()
    for p in IGNORED_PATTERNS:
        if re.search(p, lc):
            return True
    return False

def normalize_code(code):
    # basic normalization: uppercase, strip spaces
    return re.sub(r'\s+', '-', str(code).strip().upper())

def main():
    with open(PREVIEW_FILE, 'r', encoding='utf-8') as f:
        d = json.load(f)
    unknown = d.get('summary', {}).get('unknown_subjects', [])
    # filter ignored
    unknown = [u for u in unknown if not is_ignored(u)]
    if not unknown:
        print("No unknown subjects to create.")
        return

    app = create_app()
    with app.app_context():
        created = 0
        for code in unknown:
            code_norm = normalize_code(code)
            # skip if already exists in DB (normalized match)
            existing = Subject.query.get(code_norm)
            if existing:
                print("Already exists:", code_norm)
                continue
            # create placeholder subject
            s = Subject(sub_code=code_norm, sub_name=code_norm, branch=DEFAULT_BRANCH, year=DEFAULT_YEAR, semester=DEFAULT_SEMESTER)
            db.session.add(s)
            created += 1
            print("Created subject placeholder:", code_norm)
        if created:
            db.session.commit()
            print("Created", created, "subjects.")
        else:
            print("No new subjects created.")

if __name__ == "__main__":
    main()
