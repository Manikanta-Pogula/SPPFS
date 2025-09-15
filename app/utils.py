# app/utils.py
import re
from typing import Optional, Dict, List

# default weights (same as earlier)
DEFAULT_WEIGHTS = {
    'attendance': 0.10,
    'mid1': 0.15,
    'mid2': 0.15,
    'internal': 0.20,
    'end_sem': 0.40
}

def normalize_component(value: Optional[float], max_value: float) -> Optional[float]:
    if value is None:
        return None
    return (value / max_value) * 100.0

def compute_subject_score(components: Dict[str, Optional[float]], weights: Dict[str, float] = None) -> float:
    if weights is None:
        weights = DEFAULT_WEIGHTS.copy()

    max_values = {'attendance': 100.0, 'mid1': 20.0, 'mid2': 20.0, 'internal': 20.0, 'end_sem': 40.0}

    # compute percent per component (or None)
    perc = {}
    for k, maxv in max_values.items():
        perc[k] = None if components.get(k) is None else (components[k] / maxv) * 100.0

    used_weights = weights.copy()
    if perc['attendance'] is None:
        att_w = used_weights.pop('attendance', 0.0)
        total_other = sum(used_weights.values())
        if total_other > 0:
            for k in used_weights:
                used_weights[k] = used_weights[k] + (used_weights[k] / total_other) * att_w

    subject_score = 0.0
    total_weight_considered = 0.0
    for k, w in used_weights.items():
        if perc.get(k) is not None:
            subject_score += w * perc[k]
            total_weight_considered += w

    if total_weight_considered > 0 and abs(total_weight_considered - 1.0) > 1e-6:
        subject_score = subject_score / total_weight_considered

    return round(subject_score, 2)

def generate_feedback(student_name, overall_score, risk_subjects, attendance):
    feedback_parts = []

    # Overall score analysis
    if overall_score is None:
        feedback_parts.append("❌ No exam data is available yet for this student.")
    elif overall_score >= 75:
        feedback_parts.append(f"✅ Excellent performance, {student_name} is doing really well overall.")
    elif overall_score >= 60:
        feedback_parts.append(f"⚠️ {student_name} is performing moderately, but there is scope for improvement.")
    else:
        feedback_parts.append(f"🔴 {student_name} is at high risk and needs urgent academic support.")

    # Risk subjects
    if risk_subjects:
        subj_list = ", ".join(risk_subjects)
        feedback_parts.append(f"⚠️ Weak in: {subj_list}. Needs extra practice here.")

    # Attendance
    if attendance is not None:
        if attendance >= 75:
            feedback_parts.append("✅ Good attendance record.")
        elif attendance >= 60:
            feedback_parts.append("⚠️ Attendance is moderate; better consistency is required.")
        else:
            feedback_parts.append("🔴 Poor attendance; must improve class participation.")

    return " ".join(feedback_parts)


def compute_overall_score(subject_scores: List[float]) -> float:
    if not subject_scores:
        return 0.0
    return round(sum(subject_scores) / len(subject_scores), 2)

def map_risk(overall_score: float) -> str:
    if overall_score >= 70.0:
        return 'low'
    if overall_score >= 50.0:
        return 'medium'
    return 'high'

# ---------------------------
# Parsing helpers for uploads
# ---------------------------
_BREAKDOWN_RE = re.compile(r'([0-9]+(?:\.[0-9]+)?)')  # numbers in string

def parse_breakdown_cell(cell_value: str) -> Optional[Dict[str, Optional[float]]]:
    """
    Parse semester breakdown like "18+19+18+38" or "(18+19+18+38)" or "18 + 19 + 18 + 38.5"
    Returns dict with keys mid1, mid2, internal, end_sem (floats) or None if can't parse.
    """
    if cell_value is None:
        return None
    s = str(cell_value).strip()
    # remove parentheses and spaces around plus signs
    s2 = s.replace('(', '').replace(')', '').replace(' ', '')
    # Accept separators + or /
    if '+' in s2 or '/' in s2:
        parts = re.split(r'[+/]', s2)
        nums = []
        for p in parts:
            try:
                nums.append(float(p))
            except:
                nums = []
                break
        if len(nums) == 4:
            return {'mid1': nums[0], 'mid2': nums[1], 'internal': nums[2], 'end_sem': nums[3]}
        # If fewer than 4 but numeric, return as total only
    # If the cell contains 4 numbers anywhere (e.g., with text), extract them
    nums = _BREAKDOWN_RE.findall(s)
    if len(nums) >= 4:
        try:
            nums_f = [float(n) for n in nums[:4]]
            return {'mid1': nums_f[0], 'mid2': nums_f[1], 'internal': nums_f[2], 'end_sem': nums_f[3]}
        except:
            return None
    # If only one numeric value -> treat as total
    if _BREAKDOWN_RE.findall(s):
        try:
            n = float(_BREAKDOWN_RE.findall(s)[0])
            return {'total': n}
        except:
            return None
    return None
