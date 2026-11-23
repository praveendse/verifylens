from pathlib import Path
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import Page

from app.services.search_errors import SearchFailure

def scrape_article(page: Page, topic: str) -> dict:
    """Extract Wikipedia article information."""

    page.goto("https://en.wikipedia.org/wiki/Main_Page")

    search = page.locator('input[name="search"]').first
    search.fill(topic)
    search.press("Enter")

    heading = page.locator("h1#firstHeading")
    heading.wait_for()

    title = heading.inner_text()

    # Wikipedia shows its search results page when no article has this name.
    if page.locator("body.mw-special-Search, .searchresults").count() > 0:
        raise SearchFailure("no_article")

    # A disambiguation page lists several articles; there is nothing to verify.
    if page.locator("#disambigbox, .dmbox-disambig").count() > 0:
        raise SearchFailure("ambiguous")

    # Extract first meaningful paragraph
    paragraphs = page.locator(
        "#mw-content-text p"
    ).all_inner_texts()

    paragraph = next(
        (p.strip() for p in paragraphs if len(p.strip()) > 30),
        None,
    )

    if not paragraph:
        raise SearchFailure("no_text")

    # Extract available infobox fields DYNAMICALLY
    fields = {}

    infobox = page.locator("table.infobox").first

    if infobox.count() > 0:
        for row in infobox.locator("tr").all():

            header = row.locator(":scope > th")
            value = row.locator(":scope > td")

            if header.count() > 0 and value.count() > 0:
                key = header.first.inner_text().strip().lower()
                text = value.first.inner_text().strip()

                if key and text:
                    fields[key] = text

    # Locate an image
    if infobox.count() > 0:
        image = infobox.locator("img").first
    else:
        image = page.locator(
            "#mw-content-text .mw-parser-output figure img"
        ).first

    if image.count() == 0:
        raise SearchFailure("no_image")

    src = image.get_attribute("src")

    if not src:
        raise SearchFailure("no_image")

    return {
        "title": title,
        "paragraph": paragraph,
        "source_url": page.url,
        "fields": fields,
        "image_url": urljoin(page.url, src),
    }

def download_infobox_image(
    page: Page,
    image_url: str,
    download_dir: Path = Path("downloads"),
) -> Path:
    """Download the infobox image."""

    response = page.request.get(image_url)

    if not response.ok:
        raise SearchFailure("image_download")

    content_type = response.headers.get("content-type", "")

    if not content_type.startswith("image/"):
        raise SearchFailure("image_format")

    extension = Path(urlsplit(image_url).path).suffix.lower()

    if extension not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        raise SearchFailure("image_format")

    download_dir.mkdir(parents=True, exist_ok=True)

    image_path = download_dir / f"infobox_image{extension}"
    image_path.write_bytes(response.body())

    return image_path
