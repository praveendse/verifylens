from pathlib import Path
from dataclasses import dataclass

from playwright.sync_api import sync_playwright

from app.settings import Settings
from app.dto.models import ArticleDTO, VerificationDTO

from app.services.wikipedia_service import (
    scrape_article,
    download_infobox_image,
)
from app.services.gemini_service import verify_image
from app.services.report_service import generate_report

@dataclass
class PipelineResult:
    report_path: Path
    article: dict
    verification: dict

class PipelineService:
    """Coordinate the complete verification workflow."""

    def __init__(
        self,
        settings: Settings,
        scraper=scrape_article,
        downloader=download_infobox_image,
        verifier=verify_image,
        reporter=generate_report,
    ):
        self.settings = settings
        self.scraper = scraper
        self.downloader = downloader
        self.verifier = verifier
        self.reporter = reporter

    def generate_with_details(
        self,
        topic: str,
        work_dir: Path,
    ) -> Path:
        """Generate a verification report for a topic."""

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

        # Step 2: Gemini verification
        verification_data = self.verifier(
            article,
            image_path,
            api_key=self.settings.gemini_api_key,
            model=self.settings.gemini_model,
            thinking_level=self.settings.gemini_thinking_level,
            timeout_s=self.settings.gemini_timeout_seconds,
        )

        # Validate Gemini response
        verification = VerificationDTO.model_validate(
            verification_data
        ).model_dump()

        # Step 3: Generate Markdown report
        report_path = self.reporter(
            article,
            image_path,
            verification,
            work_dir / "report.md",
        )

        return PipelineResult(
            report_path=report_path,
            article=article,
            verification=verification,
        )

    def generate(self, topic: str, work_dir: Path) -> Path:
        result = self.generate_with_details(topic, work_dir)
        return result.report_path   

    
