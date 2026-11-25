# import os
from pathlib import Path

from app.dto.models import ArticleDTO, LabelCheckResult, VerificationDTO

LABEL_STATUS_TEXT = {
    "agrees": "Agrees: the labels name the article subject",
    "unclear": "Unclear: the labels don't name the article subject",
    "no_labels": "No labels to compare",
}

# Spec SRCH-15: Super mode (API value "thorough") adds these to the report.
# Standard mode keeps the original five-section report unchanged.
SUPER_MODE_LABEL = "Super mode (thorough, 2 Gemini calls)"
BLIND_NOTE = "*Written from the image alone, before Gemini saw the article.*"


def generate_report(
    article: ArticleDTO,
    image_path: Path,
    verification: VerificationDTO,
    report_path: Path = Path("report.md"),
    *,
    labels: LabelCheckResult | None = None,
    review_reason: str | None = None,
    mode: str = "standard",
) -> Path:
    """Generate a Markdown verification report."""

    def clean(value: str) -> str:
        return " ".join(value.split()).replace("|", r"\|")

    field_rows = [
        f"| {clean(key)} | {clean(value)} |"
        for key, value in article.fields.items()
    ]

    if not field_rows:
        field_rows = ["| No infobox details | Available fields not found |"]

    match_status = (
        "PASS" if verification.matches else "FAIL"
    )

    super_mode = mode == "thorough"
    labels = labels or LabelCheckResult(status="no_labels")
    label_rows = [
        f"| {name} | {clean(getattr(article, key) or '') or '—'} |"
        for key, name in (("image_caption", "Caption"), ("image_alt", "Alt text"), ("image_file", "File name"))
    ]
    label_result = LABEL_STATUS_TEXT[labels.status]
    if labels.matched_in:
        label_result += f" ({', '.join(labels.matched_in)})"

    lines = [
        f"# {article.title} - Verification Report",
        "",
        "## 1. Scraped Wikipedia Data",
        "",
        f"**Article Title:** {article.title}",
        "",
        f"**Source URL:** {article.source_url}",
        "",
        "### First Paragraph",
        "",
        article.paragraph.strip(),
        "",
        "## 2. Infobox Details",
        "",
        "| Field | Extracted Value |",
        "|---|---|",
        *field_rows,
        "",
        "## 3. Downloaded Image",
        "",
        # f"**Image Path:** {article.image_url}",
        "",
        f"**Image Source:** {article.image_url}",
        "",
        f"![Infobox Image]({article.image_url})",
        "",
        "## 4. Gemini API Verification",
        "",
        *([f"**Verification mode:** {SUPER_MODE_LABEL}", ""] if super_mode else []),
        "### Image Description",
        "",
        *([BLIND_NOTE, ""] if super_mode else []),
        verification.description,
        "",
        "### Verification Reason",
        "",
        verification.reason,
        "",
        *([
            "## 5. Wikipedia Image Labels",
            "",
            "| Label | Value |",
            "|---|---|",
            *label_rows,
            "",
            f"**Label check:** {label_result}",
            "",
        ] if super_mode else []),
        f"## {6 if super_mode else 5}. Final Verification Result",
        "",
        f"**Match Status: {match_status}**",
        "",
        *([f"**Needs review:** {review_reason}", ""] if super_mode and review_reason else []),
    ]

    report_path.parent.mkdir(parents=True, exist_ok=True)

    report_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    return report_path