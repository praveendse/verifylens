from pathlib import Path
from dataclasses import dataclass

from playwright.sync_api import sync_playwright

from app.settings import Settings
from app.dto.models import ArticleDTO, VerificationDTO

from app.services.wikipedia_service import (
    scrape_article,
    download_infobox_image,
)
from app.services.gemini_service import describe_image, verify_image
from app.services.label_check import check_labels, needs_review
from app.services.report_service import generate_report

@dataclass
class PipelineResult:
    report_path: Path
    article: dict
    verification: dict
    labels: dict | None    # label check result; None in standard mode
    review_reason: str | None = None  # set when the two checks disagree
    mode: str = "standard"  # "standard" (1 Gemini call) or "thorough" (2)

class PipelineService:
    """Coordinate the complete verification workflow."""

    def __init__(
        self,
        settings: Settings,
        scraper=scrape_article,
        downloader=download_infobox_image,
        verifier=verify_image,
        reporter=generate_report,
        describer=describe_image,
    ):
        self.settings = settings
        self.scraper = scraper
        self.downloader = downloader
        self.verifier = verifier
        self.reporter = reporter
        self.describer = describer

    def generate_with_details(
        self,
        topic: str,
        work_dir: Path,
        mode: str = "standard",
    ) -> "PipelineResult":
        """Generate a verification report for a topic.

        mode="thorough" first asks Gemini to describe the image without the
        article (spec SRCH-15), then gives that description to the verdict call.
        """
        if mode not in ("standard", "thorough"):
            raise ValueError(f"Unknown verification mode: {mode}")

        if not self.settings.gemini_api_key:
            raise ValueError("Gemini API key not found")

        work_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Scrape and download
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.settings.headless
            )

            try:
                page = browser.new_page()

                article_data = self.scraper(page, topic)

                # Validate Wikipedia data
                article = ArticleDTO.model_validate(
                    article_data
                ).model_dump()

                image_path = self.downloader(
                    page,
                    article["image_url"],
                    work_dir / "downloads",
                )

            finally:
                browser.close()

        # Step 2: Gemini verification (thorough: blind description first)
        gemini = dict(
            api_key=self.settings.gemini_api_key,
            model=self.settings.gemini_model,
            thinking_level=self.settings.gemini_thinking_level,
            timeout_s=self.settings.gemini_timeout_seconds,
        )
        blind = self.describer(image_path, **gemini) if mode == "thorough" else None
        verification_data = self.verifier(
            article,
            image_path,
            blind_description=blind,
            **gemini,
        )

        # Validate Gemini response
        verification = VerificationDTO.model_validate(
            verification_data
        ).model_dump()

        # Step 3 (Super mode only): label check, plain code independent of
        # Gemini, and the "needs review" flag when it and the verdict disagree.
        # Standard mode keeps the original behaviour.
        labels = review_reason = None
        if mode == "thorough":
            labels = check_labels(article["title"], {
                "caption": article["image_caption"],
                "alt": article["image_alt"],
                "file": article["image_file"],
            })
            review_reason = needs_review(verification["matches"], labels["status"])

        # Step 4: Generate Markdown report
        report_path = self.reporter(
            article,
            image_path,
            verification,
            work_dir / "report.md",
            labels=labels,
            review_reason=review_reason,
            mode=mode,
        )

        return PipelineResult(
            report_path=report_path,
            article=article,
            verification=verification,
            labels=labels,
            review_reason=review_reason,
            mode=mode,
        )

    def generate(self, topic: str, work_dir: Path) -> Path:
        result = self.generate_with_details(topic, work_dir)
        return result.report_path   

    
