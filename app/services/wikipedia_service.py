from pathlib import Path
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import Page

def scrape_article(page: Page, topic: str) -> dict:
    """Extract Wikipedia article information."""

    page.goto("https://en.wikipedia.org/wiki/Main_Page")

    search = page.locator('input[name="search"]').first
    search.fill(topic)
    search.press("Enter")

    heading = page.locator("h1#firstHeading")
    heading.wait_for()

    title = heading.inner_text()

    # Extract first meaningful paragraph
    paragraphs = page.locator(
        "#mw-content-text p"
    ).all_inner_texts()

    paragraph = next(
        (p.strip() for p in paragraphs if len(p.strip()) > 30),
        None,
    )

    if not paragraph:
        raise ValueError("Article paragraph not found")

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
        raise ValueError("Article image not found")

    src = image.get_attribute("src")

    if not src:
        raise ValueError("Article image URL not found")

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
        raise RuntimeError(
            f"Image download failed: {response.status}"
        )

    content_type = response.headers.get("content-type", "")

    if not content_type.startswith("image/"):
        raise ValueError("Downloaded content is not an image")

    extension = Path(urlsplit(image_url).path).suffix.lower()

    if extension not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        raise ValueError(f"Unsupported image format: {extension}")

    download_dir.mkdir(parents=True, exist_ok=True)

    image_path = download_dir / f"infobox_image{extension}"
    image_path.write_bytes(response.body())

    return image_path
