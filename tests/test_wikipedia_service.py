"""Wikipedia scraper and image download, fully offline.

A real headless Chromium runs the scraper, but every request is answered by
page.route() with the canned pages below: nothing reaches the internet.
Skipped if Playwright's Chromium is not installed.
"""
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from app.services.search_errors import SearchFailure  # noqa: E402
from app.services.wikipedia_service import download_infobox_image, scrape_article  # noqa: E402

PNG = (  # 1x1 transparent PNG
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)

MAIN_PAGE = """<html><body>
<form action="/w/index.php"><input name="search"></form>
</body></html>"""

ARTICLE_WITH_INFOBOX = """<html><body>
<h1 id="firstHeading">Eiffel Tower</h1>
<div id="mw-content-text"><div class="mw-parser-output">
<p>Short.</p>
<table class="infobox">
  <tr><th colspan="2">Eiffel Tower</th></tr>
  <tr><td colspan="2"><img src="//upload.wikimedia.org/eiffel.png"></td></tr>
  <tr><th>Location</th><td>Paris, France</td></tr>
  <tr><th>Height</th><td>330 m</td></tr>
  <tr><th>Empty</th><td></td></tr>
</table>
<p>The Eiffel Tower is a wrought-iron lattice tower on the Champ de Mars in Paris.</p>
</div></div></body></html>"""

ARTICLE_FIGURE_ONLY = """<html><body>
<h1 id="firstHeading">Some Topic</h1>
<div id="mw-content-text"><div class="mw-parser-output">
<p>This article has no infobox, only a figure further down the page.</p>
<figure><img src="/media/figure.jpg"></figure>
</div></div></body></html>"""

SEARCH_RESULTS = """<html><body class="mw-special-Search">
<h1 id="firstHeading">Search results</h1>
<div id="mw-content-text"><div class="searchresults"><p>There were no results matching the query.</p></div></div>
</body></html>"""

DISAMBIGUATION = """<html><body>
<h1 id="firstHeading">GTR</h1>
<div id="mw-content-text"><div class="mw-parser-output">
<p>GTR or GT-R may refer to several different things listed below.</p>
<div id="disambigbox">This disambiguation page lists articles associated with the title GTR.</div>
</div></div></body></html>"""

ARTICLE_NO_IMAGE = """<html><body>
<h1 id="firstHeading">Bare Topic</h1>
<div id="mw-content-text"><p>This article has a paragraph but no image at all anywhere.</p></div>
</body></html>"""


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True)
        except Exception as exc:  # browser binaries not installed
            pytest.skip(f"Playwright Chromium unavailable: {exc}")
        yield b
        b.close()


@pytest.fixture
def offline_page(browser):
    """Page whose every request is served from `responses` (url substring -> (status, type, body))."""
    context = browser.new_context()
    page = context.new_page()
    responses = {}
    requested = []

    def handle(route):
        url = route.request.url
        requested.append(url)
        for key, (status, content_type, body) in responses.items():
            if key in url:
                return route.fulfill(status=status, content_type=content_type, body=body)
        return route.fulfill(status=404, content_type="text/plain", body="not found")

    context.route("**/*", handle)
    yield page, responses, requested
    context.close()


def serve_article(responses, html):
    responses["/wiki/Main_Page"] = (200, "text/html", MAIN_PAGE)
    responses["/w/index.php"] = (200, "text/html", html)


def test_scrapes_title_paragraph_infobox_and_image(offline_page):
    page, responses, requested = offline_page
    serve_article(responses, ARTICLE_WITH_INFOBOX)

    result = scrape_article(page, "Eiffel Tower")

    assert result["title"] == "Eiffel Tower"
    assert result["paragraph"].startswith("The Eiffel Tower is a wrought-iron")  # skips the short <p>
    assert result["fields"] == {"location": "Paris, France", "height": "330 m"}  # header-only/empty rows dropped
    assert result["image_url"] == "https://upload.wikimedia.org/eiffel.png"  # protocol-relative resolved
    assert result["source_url"].startswith("https://en.wikipedia.org/w/index.php?search=Eiffel+Tower")
    # Both navigations went through the route stub (the browser's image fetch
    # from upload.wikimedia.org is stubbed too, with a 404).
    assert any("/wiki/Main_Page" in u for u in requested)
    assert any("/w/index.php?search=" in u for u in requested)


def test_falls_back_to_figure_image_without_infobox(offline_page):
    page, responses, _ = offline_page
    serve_article(responses, ARTICLE_FIGURE_ONLY)

    result = scrape_article(page, "Some Topic")

    assert result["fields"] == {}
    assert result["image_url"] == "https://en.wikipedia.org/media/figure.jpg"


def test_article_without_image_is_rejected(offline_page):
    page, responses, _ = offline_page
    serve_article(responses, ARTICLE_NO_IMAGE)

    with pytest.raises(SearchFailure) as err:
        scrape_article(page, "Bare Topic")
    assert err.value.code == "no_image"


@pytest.mark.parametrize("html, code", [(SEARCH_RESULTS, "no_article"), (DISAMBIGUATION, "ambiguous")])
def test_pages_that_are_not_one_article_are_explained(offline_page, html, code):
    page, responses, _ = offline_page
    serve_article(responses, html)

    with pytest.raises(SearchFailure) as err:
        scrape_article(page, "gtr")
    assert err.value.code == code


# download_infobox_image uses page.request (an API client that page.route does
# NOT intercept), so it gets a stub page instead of a real browser.

class _StubResponse:
    def __init__(self, status, content_type, body):
        self.status, self.ok = status, 200 <= status < 300
        self.headers = {"content-type": content_type}
        self._body = body

    def body(self):
        return self._body


class _StubPage:
    def __init__(self, response):
        self.requested = []
        page = self

        class _Request:
            def get(self, url):
                page.requested.append(url)
                return response

        self.request = _Request()


def test_downloads_image_to_work_dir(tmp_path: Path):
    page = _StubPage(_StubResponse(200, "image/png", PNG))

    path = download_infobox_image(page, "https://upload.wikimedia.org/eiffel.png", tmp_path / "downloads")

    assert page.requested == ["https://upload.wikimedia.org/eiffel.png"]
    assert path == tmp_path / "downloads" / "infobox_image.png"
    assert path.read_bytes() == PNG


@pytest.mark.parametrize(
    "url, response, code",
    [
        ("https://upload.wikimedia.org/missing.png", (404, "text/plain", b"nope"), "image_download"),
        ("https://upload.wikimedia.org/page.png", (200, "text/html", b"<html></html>"), "image_format"),
        ("https://upload.wikimedia.org/vector.svg", (200, "image/svg+xml", b"<svg/>"), "image_format"),
    ],
)
def test_bad_image_downloads_are_rejected(tmp_path: Path, url, response, code):
    page = _StubPage(_StubResponse(*response))

    with pytest.raises(SearchFailure) as err:
        download_infobox_image(page, url, tmp_path)
    assert err.value.code == code
    assert not list(tmp_path.iterdir())  # nothing written


# --- Lead image selection (SRCH-04). Markup mirrors live Wikipedia infoboxes. ---

def _infobox_article(title, cells):
    return f"""<html><body>
<h1 id="firstHeading">{title}</h1>
<div id="mw-content-text"><div class="mw-parser-output">
<table class="infobox">{cells}</table>
<p>{title} is the subject of this stub article used by the image selection tests.</p>
</div></div></body></html>"""


def _img(name, w, h, file_type="bitmap"):
    return (f'<img resource="https://en.wikipedia.org/wiki/File:{name}" src="//upload.wikimedia.org/{name}.png" '
            f'width="{w}" height="{h}" data-file-type="{file_type}">')


LANDMARK_WITH_LOGO = _infobox_article("Eiffel Tower", f"""
  <tr><td class="infobox-image">{_img("Eiffel_Tower_logo.svg", 120, 154, "drawing")}</td></tr>
  <tr><td class="infobox-image">{_img("Tour_Eiffel.jpg", 280, 466)}</td></tr>
  <tr><td class="infobox-image">{_img("location_map.svg", 250, 200, "drawing")}</td></tr>""")

COMPANY_WITH_LOGO = _infobox_article("Toyota", f"""
  <tr><td class="infobox-image ib-company-logo logo">{_img("Toyota.svg", 250, 41, "drawing")}</td></tr>
  <tr><td class="infobox-image ib-company-logo logo">{_img("Toyota_HQ.jpg", 250, 333)}</td></tr>""")

ONLY_A_LOGO = _infobox_article("Python", f"""
  <tr><td class="infobox-image">{_img("Python-logo-notext.svg", 150, 150, "drawing")}</td></tr>""")

ICONS_BEFORE_IMAGE = _infobox_article("Taj Mahal", f"""
  <tr><td class="infobox-image">{_img("Codex_icon_map.svg", 20, 20, "drawing")}</td></tr>
  <tr><td class="infobox-image">{_img("Taj_Mahal.jpeg", 250, 164)}</td></tr>""")

COLLAGE_WITHOUT_IMAGE_CELL = _infobox_article("World War II", f"""
  <tr><td class="infobox-data">{_img("Increase2.svg", 11, 11, "drawing")}</td></tr>
  <tr><td><div class="collage">{_img("Junkers_planes.jpg", 169, 115)}{_img("Matilda_tanks.jpg", 115, 116)}</div></td></tr>""")


@pytest.mark.parametrize("html, topic, expected", [
    (LANDMARK_WITH_LOGO, "Eiffel Tower", "Tour_Eiffel.jpg"),        # landmark logo skipped
    (COMPANY_WITH_LOGO, "Toyota", "Toyota.svg"),                    # company logo kept, even when short and wide
    (ONLY_A_LOGO, "Python", "Python-logo-notext.svg"),              # a logo is used when it is the only image
    (ICONS_BEFORE_IMAGE, "Taj Mahal", "Taj_Mahal.jpeg"),            # icons skipped
    (COLLAGE_WITHOUT_IMAGE_CELL, "World War II", "Junkers_planes.jpg"),  # no image cell: first non-icon image
])
def test_picks_the_infobox_lead_image(offline_page, html, topic, expected):
    page, responses, _ = offline_page
    serve_article(responses, html)

    result = scrape_article(page, topic)

    assert result["image_url"] == f"https://upload.wikimedia.org/{expected}.png"


def test_infobox_with_only_icons_has_no_image(offline_page):
    page, responses, _ = offline_page
    serve_article(responses, _infobox_article("Icons", f'<tr><td class="infobox-data">{_img("Increase2.svg", 11, 11)}</td></tr>'))

    with pytest.raises(SearchFailure) as err:
        scrape_article(page, "Icons")
    assert err.value.code == "no_image"


def test_returns_the_chosen_images_labels(offline_page):
    """Caption from the same cell as the chosen image, not the skipped logo's."""
    page, responses, _ = offline_page
    serve_article(responses, _infobox_article("Eiffel Tower", f"""
  <tr><td class="infobox-image">{_img("Eiffel_Tower_logo.svg", 120, 154, "drawing")}
      <div class="infobox-caption">Logo caption</div></td></tr>
  <tr><td class="infobox-image">{_img("Tour_Eiffel_(cropped).jpg", 280, 466).replace("<img ", '<img alt="The tower " ')}
      <div class="infobox-caption">Seen from the   Champ de Mars, 2009</div></td></tr>"""))

    result = scrape_article(page, "Eiffel Tower")

    assert result["image_caption"] == "Seen from the Champ de Mars, 2009"  # whitespace collapsed
    assert result["image_alt"] == "The tower"
    assert result["image_file"] == "Tour_Eiffel_(cropped).jpg"


def test_figure_image_labels_and_missing_labels(offline_page):
    page, responses, _ = offline_page
    serve_article(responses, ARTICLE_FIGURE_ONLY.replace(
        '<figure><img src="/media/figure.jpg"></figure>',
        '<figure><img src="/media/330px-Some_Topic.jpg"><figcaption>Some Topic in 2020</figcaption></figure>'))

    result = scrape_article(page, "Some Topic")

    assert result["image_caption"] == "Some Topic in 2020"
    assert result["image_alt"] is None
    assert result["image_file"] == "Some_Topic.jpg"  # thumbnail size prefix removed
