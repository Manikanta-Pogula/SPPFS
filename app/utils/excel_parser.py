# app/utils/excel_parser.py
"""
Robust parser for uploaded CSV/XLSX mark files.

This version:
 - marks component-level absences as None internally
 - sets preview display strings using "AB" for absent components
 - extracts numeric breakdowns from "(a+b+c+d)", "a/b/c/d", "a+b+c+d"
 - if the top cell is a letter grade it will look to the next row for numeric breakdown
 - returns:
     {"subject_cols": [...], "meta_cols":[...], "rows":[{"pin","name","attendance","meta","subjects":[{sub_code,raw_mark,absent,parsed_components,display,error}], "row_errors":[...]}]}
"""
import io
import re
from typing import Dict, Any, List
import pandas as pd

# Meta keywords to treat as non-subject columns
META_KEYWORDS = ['rubric', 'total', 'credit', 'sgpa', 'cgpa', 'result', 'attendance', 'remarks', 'grade']

# header words to detect header row presence
HEADER_KEYWORDS = ['pin', 'usn', 'roll', 'register', 'reg', 'student id', 'registration', 'sap', 'admission', 'enrol']

# numeric token regex (captures integers and decimals, optionally negative)
NUM_RE = re.compile(r'[-+]?\d+(?:\.\d+)?', flags=re.IGNORECASE)

# absence tokens (explicit)
ABSENT_TOKENS = {'AB', 'ABS', 'ABSENT'}

def _normalize_col(c):
    return str(c).strip() if c is not None else ''

def _is_meta_col(colname: str) -> bool:
    if not colname:
        return False
    s = colname.lower()
    for kw in META_KEYWORDS:
        if kw in s:
            return True
    return False

def _looks_like_pin_header_row(row_values: List[str]) -> bool:
    for v in row_values:
        if not isinstance(v, str):
            continue
        s = v.strip().lower()
        for kw in HEADER_KEYWORDS:
            if kw in s:
                return True
    return False

def _find_header_row_index(df_no_header: pd.DataFrame) -> int:
    max_check = min(15, len(df_no_header))
    for i in range(max_check):
        row = df_no_header.iloc[i].astype(str).tolist()
        if _looks_like_pin_header_row(row):
            return i
    # fallback: first non-empty row
    return 0

def _extract_numbers_from_text(s: str) -> List[float]:
    if s is None:
        return []
    nums = NUM_RE.findall(str(s))
    try:
        return [float(x) for x in nums]
    except:
        return []

def _parse_parenthesis_or_slash_or_plus_numbers(s: str) -> List[Any]:
    """
    Extract numeric tokens from strings like (15+15+18+38.5) or '20/20/10/50' or '15+15+18+38.5'.
    Return list of floats or None (for explicit AB), empty list if none found.
    """
    if s is None:
        return []
    st = str(s)
    # If parentheses present, extract inside
    inside = st
    if '(' in st and ')' in st:
        start = st.find('(')
        end = st.rfind(')')
        inside = st[start+1:end]
    # split by common delimiters
    parts = re.split(r'[+/]', inside)
    result = []
    for p in parts:
        p = p.strip()
        if p == '':
            continue
        up = p.upper().replace('.', '').replace(' ', '')
        if up in ABSENT_TOKENS or up == 'AB' or up == 'A B':
            result.append(None)
            continue
        nums = NUM_RE.findall(p)
        if nums:
            try:
                result.append(float(nums[-1]))
                continue
            except:
                pass
        result.append(None)
    return result

def _is_explicit_absent_token(s: str) -> bool:
    if s is None:
        return False
    st = str(s).strip().upper().replace('.', '').replace(' ', '')
    return st in ABSENT_TOKENS

def _parse_cell_value(cell, following_cell=None):
    """
    Return (raw_value: Optional[float], absent: bool, parsed_components: Optional[dict], display_text: str, error: Optional[str])
    - parsed_components: dict(mid1, mid2, internal, end_sem) if breakdown available (may contain None for absent)
    - raw_value: numeric value to use as end_sem if available (or None)
    - absent: True only when explicit absent token found for the cell
    - display_text: user-friendly string to display (like "20/20/10/50" or "A+" or "AB")
    - error: textual error
    """
    # empty cell
    if pd.isna(cell) or str(cell).strip() == "":
        return None, False, None, "", None

    s = str(cell).strip()
    su = s.upper().strip()

    # explicit absent tokens -> mark absent and show "AB"
    if _is_explicit_absent_token(s):
        return 0.0, True, None, "AB", None

    # If the cell contains any digits, try to parse numeric patterns first
    if NUM_RE.search(s):
        # slash-separated e.g. '20/20/10/50'
        if '/' in s:
            parts = [p.strip() for p in s.split('/') if p.strip() != ""]
            nums = []
            for p in parts:
                n = NUM_RE.findall(p)
                if n:
                    try:
                        nums.append(float(n[-1]))
                    except:
                        nums.append(None)
                else:
                    nums.append(None)
            if len(nums) >= 4:
                parsed = {"mid1": nums[0], "mid2": nums[1], "internal": nums[2], "end_sem": nums[3]}
                display = "/".join("AB" if x is None else (str(int(x)) if float(x).is_integer() else str(x)) for x in nums[:4])
                raw = parsed['end_sem'] if parsed['end_sem'] is not None else None
                return raw, False, parsed, display, None
            try:
                first = float(parts[0])
                display = "/".join(parts)
                if first.is_integer():
                    display_first = str(int(first))
                else:
                    display_first = str(first)
                return first, False, None, display, None
            except:
                return None, False, None, "/".join(parts), None

        # parentheses or plus-separated numbers
        parsed_nums = _parse_parenthesis_or_slash_or_plus_numbers(s)
        if parsed_nums and any(x is not None for x in parsed_nums):
            if len(parsed_nums) >= 4:
                nums4 = parsed_nums[:4]
                parsed = {"mid1": nums4[0], "mid2": nums4[1], "internal": nums4[2], "end_sem": nums4[3]}
                display = "/".join("AB" if x is None else (str(int(x)) if float(x).is_integer() else str(x)) for x in nums4)
                raw = parsed['end_sem']
                return raw, False, parsed, display, None
            else:
                last_num = None
                for v in parsed_nums:
                    if v is not None:
                        last_num = v
                display = "/".join("AB" if x is None else (str(int(x)) if float(x).is_integer() else str(x)) for x in parsed_nums)
                return last_num, False, None, display, None

        # fallback plain numeric
        try:
            v = float(NUM_RE.findall(s)[-1])
            display = str(int(v)) if float(v).is_integer() else str(v)
            return v, False, None, display, None
        except Exception:
            return None, False, None, s, "unparseable numeric-like cell"

    # If cell has NO digits (likely a letter grade like 'A' or 'A+'), do NOT mark absent.
    # Instead, look at following_cell for numeric breakdown if present
    if following_cell is not None:
        if NUM_RE.search(str(following_cell)):
            parsed_nums = _parse_parenthesis_or_slash_or_plus_numbers(following_cell)
            if parsed_nums and any(x is not None for x in parsed_nums):
                if len(parsed_nums) >= 4:
                    nums4 = parsed_nums[:4]
                    parsed = {"mid1": nums4[0], "mid2": nums4[1], "internal": nums4[2], "end_sem": nums4[3]}
                    display = "/".join("AB" if x is None else (str(int(x)) if float(x).is_integer() else str(x)) for x in nums4)
                    raw = parsed['end_sem']
                    return raw, False, parsed, display, None
                else:
                    last_num = None
                    for v in parsed_nums:
                        if v is not None:
                            last_num = v
                    display = "/".join("AB" if x is None else (str(int(x)) if float(x).is_integer() else str(x)) for x in parsed_nums)
                    return last_num, False, None, display, None

    # otherwise treat as letter grade or text; show it (not absent)
    # we return display as given text (e.g. 'A+', 'B', 'P')
    return None, False, None, s, None

def parse_uploaded_workbook(file_stream: io.BytesIO, filename_hint: str = None) -> Dict[str, Any]:
    """
    Parse uploaded file (csv/xlsx) and return normalized preview structure.
    """
    buf = file_stream
    is_csv = False
    if filename_hint and filename_hint.lower().endswith('.csv'):
        is_csv = True

    buf.seek(0)
    try:
        if is_csv:
            df0 = pd.read_csv(buf, header=None, dtype=str, keep_default_na=False)
            header_row = 0
            buf.seek(0)
            df = pd.read_csv(buf, header=header_row, dtype=str, keep_default_na=False)
        else:
            df0 = pd.read_excel(buf, header=None, engine='openpyxl', dtype=str)
            header_row = _find_header_row_index(df0)
            buf.seek(0)
            df = pd.read_excel(buf, header=header_row, engine='openpyxl', dtype=str)
    except Exception:
        buf.seek(0)
        try:
            df = pd.read_csv(buf, dtype=str, keep_default_na=False)
        except Exception as e:
            raise

    # normalize column names
    cols = [_normalize_col(c) for c in df.columns.tolist()]
    lower_cols = [c.lower() for c in cols]

    # identify pin and name columns
    pin_col = None
    name_col = None
    for idx, c in enumerate(cols):
        lc = c.lower()
        if any(kw in lc for kw in HEADER_KEYWORDS):
            pin_col = cols[idx]
            break
    if not pin_col:
        for c in cols:
            if c.strip().lower() in ('pin','usn','registration no','registration','reg no','roll no','roll'):
                pin_col = c
                break
    for c in cols:
        if c.strip().lower() in ('name','student name','student'):
            name_col = c
            break
    if not name_col:
        for c in cols:
            if 'name' in c.lower():
                name_col = c
                break

    # classify columns as subject vs meta
    subject_cols = []
    meta_cols = []
    for c in cols:
        if c == pin_col or c == name_col:
            continue
        if _is_meta_col(c) or any(kw in c.lower() for kw in META_KEYWORDS):
            meta_cols.append(c)
        else:
            if c is None or str(c).strip() == '':
                continue
            subject_cols.append(c)

    normalized_rows = []
    L = len(df)
    i = 0
    while i < L:
        row = df.iloc[i]
        # get pin and name
        pin_val = None
        if pin_col and pin_col in df.columns:
            pin_val = row.get(pin_col)
        else:
            pin_val = row.iloc[0] if len(row) > 0 else None
        name_val = None
        if name_col and name_col in df.columns:
            name_val = row.get(name_col)
        else:
            if len(row) > 1:
                try:
                    name_val = row.iloc[1]
                except:
                    name_val = ''

        pin = str(pin_val).strip() if pin_val is not None and str(pin_val).strip().lower() not in ('nan','') else ''
        name = str(name_val).strip() if name_val is not None and str(name_val).strip().lower() not in ('nan','') else ''

        if not pin:
            i += 1
            continue

        # attendance
        attendance_val = None
        for c in df.columns:
            if str(c).strip().lower() == 'attendance':
                a = row.get(c)
                try:
                    attendance_val = float(a) if a is not None and str(a).strip()!='' else None
                except:
                    attendance_val = a
                break

        # meta values
        meta_values = {}
        for mc in meta_cols:
            v = row.get(mc)
            meta_values[mc] = None if (v is None or str(v).strip() in ('', 'nan')) else v

        subjects_preview = []
        row_errors = []
        next_row = df.iloc[i+1] if i+1 < L else None

        for sc in subject_cols:
            cell = row.get(sc)
            following = next_row.get(sc) if next_row is not None and sc in next_row.index else None
            raw_val, absent, parsed_components, display_text, error = _parse_cell_value(cell, following)
            if error:
                row_errors.append(f"{sc}: {error}")
            # If parsed_components present, ensure display_text uses "AB" for None parts (already handled in parser)
            subjects_preview.append({
                "sub_code": sc,
                "raw_mark": raw_val,
                "absent": absent,
                "parsed_components": parsed_components,
                "display": display_text,
                "error": error
            })

        normalized_rows.append({
            "pin": pin,
            "name": name,
            "attendance": attendance_val,
            "meta": meta_values,
            "subjects": subjects_preview,
            "row_errors": row_errors
        })

        # skip next row if it is a breakdown (no pin and many numeric-like cells)
        skip_next = False
        if next_row is not None:
            next_pin = None
            if pin_col and pin_col in df.columns:
                next_pin = next_row.get(pin_col)
            if next_pin is None or str(next_pin).strip() == '':
                count_num_like = 0
                check_cols = subject_cols[:6] if len(subject_cols) > 6 else subject_cols
                for sc in check_cols:
                    v = next_row.get(sc)
                    if v is None:
                        continue
                    if NUM_RE.search(str(v)):
                        count_num_like += 1
                if count_num_like >= 1:
                    skip_next = True

        i += 2 if skip_next else 1

    return {"subject_cols": subject_cols, "meta_cols": meta_cols, "rows": normalized_rows}
