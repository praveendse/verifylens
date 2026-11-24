import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

from playwright.sync_api import Page

from app.services.search_errors import SearchFailure

# Picks the infobox's lead image (spec SRCH-04). The first <img> is not always
# it: landmark infoboxes can show the landmark's logo above its photo (Eiffel
# Tower, Burj Khalifa, Sydney Opera House), and infoboxes contain small icons
# (trend arrows, map pins). Rules, checked against 35 live articles:
#   1. Only images in the infobox's image cells (td.infobox-image) count.
#   2. Skip icons: under 50 px on both sides.
#   3. Skip a logo when a real image follows, except in company infoboxes
#      (td.ib-company-logo), where the logo is the intended lead image.
#   4. No usable image cell (e.g. a collage): first non-icon image anywhere
#      in the infobox.
PICK_LEAD_IMAGE_JS = """
ib => {
  const MIN = 50;
  const name = img => decodeURIComponent(
    (img.getAttribute('resource') || img.getAttribute('src') || '').split('/').pop());
  const dim = (img, attr) => parseInt(img.getAttribute(attr), 10);
  const isIcon = img => dim(img, 'width') < MIN && dim(img, 'height') < MIN;
  const isLogo = img => /logo/i.test(name(img)) ||
    (img.getAttribute('data-file-type') === 'drawing' && !!img.closest('td.logo'));
  const companyLogo = img => !!img.closest('td.ib-company-logo');
  const usable = imgs => imgs.filter(img => !isIcon(img));

  const lead = usable([...ib.querySelectorAll('td.infobox-image img')]);
  const pick = lead.find(img => !isLogo(img) || companyLogo(img)) || lead[0]
            || usable([...ib.querySelectorAll('img')])[0];
  if (!pick) return null;
  // Labels of the chosen image only: the caption sits in the same cell.
  const cell = pick.closest('td');
  const caption = cell && cell.querySelector('.infobox-caption');
  return {
    src: pick.getAttribute('src'),
    caption: caption ? caption.textContent : null,
    alt: pick.getAttribute('alt'),
    resource: pick.getAttribute('resource'),
  };
}
"""

# Same labels for the first article figure, used when there is no infobox.
FIGURE_IMAGE_JS = """
fig => {
  const img = fig.querySelector('img');
  const caption = fig.querySelector('figcaption');
  return img ? {
    src: img.getAttribute('src'),
    caption: caption ? caption.textContent : null,
    alt: img.getAttribute('alt'),
    resource: img.getAttribute('resource'),
  } : null;
}
"""


def _clean(text: str | None) -> str | None:
    """Collapse whitespace; blank becomes None."""
    text = " ".join((text or "").split())
    return text or None


def image_file_name(src: str, resource: str | None = None) -> str:
    """The image's file name on Wikipedia, e.g. 'Tour_Eiffel_(cropped).jpg'.

    Prefers the File: page link; otherwise the URL's last part without the
    thumbnail size prefix ('330px-').
    """
    if resource and "File:" in resource:
        return unquote(resource.split("File:", 1)[1])
    name = unquote(urlsplit(src).path.rsplit("/", 1)[-1])
    return re.sub(r"^\d+px-", "", name)


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

    # Locate the lead image (Task 1: "the infobox lead image") and its labels
    if infobox.count() > 0:
        picked = infobox.evaluate(PICK_LEAD_IMAGE_JS)
    else:
        figure = page.locator("#mw-content-text .mw-parser-output figure").first
        picked = figure.evaluate(FIGURE_IMAGE_JS) if figure.count() > 0 else None

    src = picked["src"] if picked else None
    if not src:
        raise SearchFailure("no_image")

    return {
        "title": title,
        "paragraph": paragraph,
        "source_url": page.url,
        "fields": fields,
        "image_url": urljoin(page.url, src),
        # Wikipedia's own labels for the chosen image (spec SRCH-14)
        "image_caption": _clean(picked.get("caption")),
        "image_alt": _clean(picked.get("alt")),
        "image_file": image_file_name(src, picked.get("resource")),
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
