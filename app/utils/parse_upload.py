# helper: app/utils/excel_parser.py  (drop into your app/utils/)
import re
import io
import pandas as pd

PIN_RE = re.compile(r'\d{3,}-[A-Za-z]+-\d{1,}')  # permissive PIN pattern; adapt if needed
PAREN_RE = re.compile(r'[\d]+(?:\.[\d]+)?')

BASE_COLS = set(['pin','name','attendance','rubrics','total','credits','total grade points','sgpa','cgpa','result'])

def _find_header_row_xlsx(df_no_header):
    # df_no_header: DataFrame read with header=None
    for i in range(min(12, len(df_no_header))):  # check first 12 rows
        row = df_no_header.iloc[i].astype(str).str.lower().tolist()
        if 'pin' in [c.strip() for c in row]:
            return i
    # fallback
    return 0

def _parse_mark_cell(cell, following_cell=None):
    """Return (value: float|None, absent: bool, error: str|None)"""
    if pd.isna(cell) or str(cell).strip()=='':
        return None, False, None

    s = str(cell).strip()
    # common absent markers
    if s.upper() in ('A','ABSENT','AB'):
        return 0.0, True, None

    # if it's numeric (int/float string)
    try:
        val = float(s)
        # guard against weird negative sentinel values like -3 or large negative numbers which sometimes indicate missing
        if val < 0 and abs(val) < 100:  # treat small negative as error/missing
            return None, False, 'unexpected negative'
        return val, False, None
    except:
        pass

    # if the cell is a letter grade e.g. "A+" -> try to use following_cell for breakdown "(15+15+...)".
    if following_cell is not None and isinstance(following_cell, str) and '(' in following_cell:
        nums = PAREN_RE.findall(following_cell)
        if nums:
            total = sum(float(x) for x in nums)
            return total, False, None

    # if cell itself contains parentheses with numbers
    if '(' in s:
        nums = PAREN_RE.findall(s)
        if nums:
            return sum(float(x) for x in nums), False, None

    # last resort: attempt to extract any number inside the string
    nums = PAREN_RE.findall(s)
    if nums:
        val = sum(float(x) for x in nums)
        return val, False, None

    return None, False, 'non-numeric/unknown format'

def parse_uploaded_workbook(file_bytes, filename_hint=None):
    """
    Accepts bytes (e.g., request.files['file'].read()) and returns:
      { 'headers': [...subject columns...], 'rows': [
          { 'pin':..., 'name':..., 'attendance':..., 'subjects': [{ 'sub_code':..., 'raw':..., 'absent':..., 'error':... }, ...], 'row_errors': [...] }
      ] }
    """
    buf = io.BytesIO(file_bytes)
    # read without header to find header row
    xls = pd.read_excel(buf, header=None, engine='openpyxl')
    header_row = _find_header_row_xlsx(xls)
    # re-read with header
    buf.seek(0)
    df = pd.read_excel(buf, header=header_row, engine='openpyxl')
    # normalize column names
    cols = [str(c).strip() for c in df.columns.tolist()]

    # create lower-case set to detect special columns
    lower_cols = [c.lower() for c in cols]
    subject_cols = [c for c in cols if c.lower() not in BASE_COLS]

    normalized_rows = []
    i = 0
    L = len(df)
    while i < L:
        row = df.iloc[i]
        pin = str(row.get('Pin') or row.get('PIN') or row.get('pin') or '').strip()
        name = str(row.get('Name') or row.get('NAME') or row.get('name') or '').strip()
        # If this row has no PIN, skip it (it may be a breakdown row)
        if not pin or not PIN_RE.search(pin):
            i += 1
            continue

        # attempt to read following row (for breakdowns)
        next_row = df.iloc[i+1] if i+1 < L else None

        attendance_raw = None
        if 'Attendance' in df.columns:
            a = row.get('Attendance')
            if pd.notna(a):
                try:
                    attendance_raw = float(a)
                except:
                    attendance_raw = None

        row_errors = []
        subjects_preview = []
        for sc in subject_cols:
            cell = row.get(sc)
            following = None
            if next_row is not None:
                following = next_row.get(sc)
            val, absent, err = _parse_mark_cell(cell, following)
            subjects_preview.append({
                'sub_code': sc,
                'raw_mark': val,
                'absent': absent,
                'error': err
            })
            if err:
                row_errors.append(f"{sc}: {err}")

        normalized_rows.append({
            'pin': pin,
            'name': name,
            'attendance': attendance_raw,
            'subjects': subjects_preview,
            'row_errors': row_errors
        })

        # If next_row seems to be the parentheses-breakdown row, skip it too
        # Heuristic: next_row has no Pin but contains parentheses for subject columns
        skip_next = False
        if next_row is not None:
            next_pin = str(next_row.get('Pin') or '').strip()
            if not next_pin:
                # if at least one subject col in next_row is like '(15+15+...)', skip it
                for sc in subject_cols[:6]:  # check some columns
                    v = next_row.get(sc)
                    if isinstance(v, str) and '(' in v:
                        skip_next = True
                        break
        i += 2 if skip_next else 1

    return {'subject_cols': subject_cols, 'rows': normalized_rows}
