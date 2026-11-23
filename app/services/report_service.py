# import os
from pathlib import Path

def generate_report(
    article: dict,
    image_path: Path,
    verification: dict,
    report_path: Path = Path("report.md"),
) -> Path:
    """Generate a Markdown verification report."""

    fields = article["fields"]

    def clean(value: str) -> str:
        return " ".join(value.split()).replace("|", r"\|")

    field_rows = [
        f"| {clean(key)} | {clean(value)} |"
        for key, value in article["fields"].items()
    ]

    if not field_rows:
        field_rows = ["| No infobox details | Available fields not found |"]

    match_status = (
        "PASS" if verification["matches"] else "FAIL"
    )

    lines = [
        f"# {article['title']} - Verification Report",
        "",
        "## 1. Scraped Wikipedia Data",
        "",
        f"**Article Title:** {article['title']}",
        "",
        f"**Source URL:** {article['source_url']}",
        "",
        "### First Paragraph",
        "",
        article["paragraph"].strip(),
        "",
        "## 2. Infobox Details",
        "",
        "| Field | Extracted Value |",
        "|---|---|",
        *field_rows,
        "",
        "## 3. Downloaded Image",
        "",
        # f"**Image Path:** {article['image_url']}",
        "",
        f"**Image Source:** {article['image_url']}",
        "",
        f"![Infobox Image]({article['image_url']})",
        "",
        "## 4. Gemini API Verification",
        "",
        "### Image Description",
        "",
        verification["description"],
        "",
        "### Verification Reason",
        "",
        verification["reason"],
        "",
        "## 5. Final Verification Result",
        "",
        f"**Match Status: {match_status}**",
        "",
    ]

    report_path.parent.mkdir(parents=True, exist_ok=True)

    report_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    return report_path