# app/utils/grades.py
"""
Canonical grading utilities for SPPFS.

Functions:
 - compute_subject_score(components, absent_flags) -> float (0-100)
 - compute_flags(components, absent_flags) -> dict(mid_fail, backlog)
 - compute_eligibility(attendance) -> "Eligible"/"Condonation"/"Ineligible"/None
 - compute_overall_score(list_of_scores) -> float
"""

from typing import Optional, Dict, List

_MAX_MARKS = {"mid1": 20.0, "mid2": 20.0, "internal": 20.0, "end_sem": 40.0}
_BASE_WEIGHTS = {"mid1": 0.2, "mid2": 0.2, "internal": 0.2, "end_sem": 0.4}


def compute_subject_score(components: Dict[str, Optional[float]],
                          absent_flags: Optional[Dict[str, bool]] = None) -> float:
    if absent_flags is None:
        absent_flags = {}

    total_weighted_pct = 0.0
    total_used_weight = 0.0

    for comp, base_w in _BASE_WEIGHTS.items():
        v = components.get(comp)
        is_absent = absent_flags.get(comp, False)

        if v is None:
            if is_absent:
                pct = 0.0
                total_weighted_pct += pct * base_w
                total_used_weight += base_w
            else:
                # exam not held -> exclude component (rescale remaining)
                continue
        else:
            max_m = _MAX_MARKS.get(comp, 1.0)
            try:
                pct = (float(v) / max_m) * 100.0
            except Exception:
                pct = 0.0
            total_weighted_pct += pct * base_w
            total_used_weight += base_w

    if total_used_weight == 0:
        return 0.0
    final_pct = total_weighted_pct / total_used_weight
    return round(final_pct, 2)


def compute_flags(components: Dict[str, Optional[float]],
                  absent_flags: Optional[Dict[str, bool]] = None) -> Dict[str, bool]:
    if absent_flags is None:
        absent_flags = {}

    def val_or_zero_if_absent(c):
        v = components.get(c)
        if v is None and absent_flags.get(c, False):
            return 0.0
        return v

    mid_fail = False
    m1 = val_or_zero_if_absent("mid1")
    m2 = val_or_zero_if_absent("mid2")
    if (m1 is not None and m1 < 7.0) or (m2 is not None and m2 < 7.0):
        mid_fail = True

    backlog = False
    endv = val_or_zero_if_absent("end_sem")
    if (endv is not None and endv < 14.0) or absent_flags.get("end_sem", False):
        backlog = True

    return {"mid_fail": mid_fail, "backlog": backlog}


def compute_eligibility(attendance: Optional[float]) -> Optional[str]:
    if attendance is None:
        return None
    try:
        a = float(attendance)
    except Exception:
        return None
    if a >= 75.0:
        return "Eligible"
    if 65.0 <= a < 75.0:
        return "Condonation"
    return "Ineligible"


def compute_overall_score(subject_scores: List[float]) -> float:
    if not subject_scores:
        return 0.0
    return round(sum(subject_scores) / len(subject_scores), 2)


def normalize_absent_marks(components):
    """
    Replace None (absent) marks with 0.0 for DB safety,
    and return a tuple of (normalized_components, flags)
    flags = {'mid_fail': bool, 'backlog': bool}
    """
    normalized = {}
    flags = {'mid_fail': False, 'backlog': False}

    for key in ['mid1', 'mid2', 'internal', 'end_sem']:
        val = components.get(key)
        if val is None:
            normalized[key] = 0.0
        else:
            normalized[key] = float(val)

    # Apply business rules
    if normalized['mid1'] < 7 or normalized['mid2'] < 7:
        flags['mid_fail'] = True
    if normalized['end_sem'] < 14:
        flags['backlog'] = True

    return normalized, flags
