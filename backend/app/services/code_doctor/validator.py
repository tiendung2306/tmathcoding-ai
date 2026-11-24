"""Turn model output into a report the teacher can trust.

Following the GPT4Hints validation idea, claims are checked before they are
shown: a logic error must point at real lines of the submission, lists are
bounded, and the confidence drops when evidence is missing.
"""

from __future__ import annotations

from app.schemas.code_doctor import (
    DoctorFinding, DoctorLLMOutput, DoctorLogicError, DoctorReportData,
)

MAX_TEXT = 600
LIMITS = {"strengths": 5, "weaknesses": 6, "logic_errors": 5, "student_hints": 3}
CONFIDENCE_ORDER = ["low", "medium", "high"]


def clean_text(value: str | None) -> str:
    text = " ".join((value or "").split())
    text = text.replace("—", ", ").replace("–", "-")
    return text[:MAX_TEXT].strip()


def valid_lines(lines: list[int] | None, line_count: int) -> list[int]:
    out = []
    for line in lines or []:
        try:
            number = int(line)
        except (TypeError, ValueError):
            continue
        if 1 <= number <= line_count and number not in out:
            out.append(number)
    return sorted(out)[:8]


def _lower(confidence: str, ceiling: str) -> str:
    return CONFIDENCE_ORDER[min(CONFIDENCE_ORDER.index(confidence), CONFIDENCE_ORDER.index(ceiling))]


def apply_model_output(report: DoctorReportData, output: DoctorLLMOutput, line_count: int,
                       risk_lines: set[int]) -> DoctorReportData:
    """Fill the model-written parts of ``report`` after validating them."""
    dropped = 0
    strengths = []
    for item in output.strengths[:LIMITS["strengths"]]:
        text = clean_text(item.point)
        if text:
            strengths.append(DoctorFinding(point=text, lines=valid_lines(item.lines, line_count)))
    weaknesses = []
    for item in output.weaknesses[:LIMITS["weaknesses"]]:
        text = clean_text(item.point)
        if text:
            weaknesses.append(DoctorFinding(point=text, lines=valid_lines(item.lines, line_count), severity=item.severity))
    errors = []
    for item in output.logic_errors:
        lines = valid_lines(item.lines, line_count)
        what, why, fix = clean_text(item.what), clean_text(item.why), clean_text(item.fix)
        if not lines or not what:
            dropped += 1  # a logic error without a real location is not shown
            continue
        if report.verdict == "AC":
            # Tests accepted the program: report it as an untested risk, not as a bug.
            weaknesses.append(DoctorFinding(point=f"Rủi ro chưa bị test phát hiện: {what}. {why}".strip(),
                                            lines=lines, severity="medium"))
            continue
        evidence = "static" if risk_lines & set(lines) else ("reference_diff" if report.nearest_approach else "model")
        errors.append(DoctorLogicError(lines=lines, what=what, why=why, fix=fix, evidence=evidence))
    errors = errors[:LIMITS["logic_errors"]]

    report.overview = clean_text(output.overview) or report.overview
    report.direction = output.direction
    report.strengths = strengths
    report.weaknesses = weaknesses[:LIMITS["weaknesses"]]
    report.logic_errors = errors
    report.student_hints = [clean_text(h) for h in output.student_hints if clean_text(h)][:LIMITS["student_hints"]]
    confidence = output.confidence
    if output.time_complexity:
        report.estimated_complexity = clean_text(output.time_complexity)[:64]
    if dropped:
        report.limitations.append(f"Đã bỏ {dropped} nhận xét lỗi không chỉ ra được dòng mã cụ thể.")
    if report.verdict not in ("AC", "CE") and not errors:
        confidence = _lower(confidence, "low")
        report.limitations.append("Chưa xác định được vị trí sai cụ thể trong mã.")
    if report.nearest_approach is None:
        confidence = _lower(confidence, "medium")
    report.confidence = confidence
    return report
