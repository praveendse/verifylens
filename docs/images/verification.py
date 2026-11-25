"""Generate docs/images/verification.svg and verification.png.

Run from the project root:  python docs/images/verification.py
Shows the verification modes and the label check (spec SRCH-14, SRCH-15),
as implemented in backend/app/services/pipeline_service.py. Arrows show data flow.
Uses the Playwright Chromium the app already installs.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
W, H = 1450, 650
INK, MUTED, LINE = "#0f172a", "#475569", "#334155"
FONT = "Noto Sans, Liberation Sans, Arial, sans-serif"
out: list[str] = []


def text(x, y, lines, size=14, bold_first=True, color=INK, anchor="middle"):
    for i, line in enumerate(lines):
        weight = 700 if (i == 0 and bold_first) else 400
        fill = color if (i == 0 or not bold_first) else MUTED
        s = size if i == 0 else size - 1.5
        out.append(f'<text x="{x}" y="{y + i * (size + 5)}" font-size="{s}" font-weight="{weight}" '
                   f'fill="{fill}" text-anchor="{anchor}">{line}</text>')


def box(x, y, w, h, lines, fill="#ffffff", stroke=LINE, color=INK, bold_first=True):
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" '
               f'stroke="{stroke}" stroke-width="1.5"/>')
    top = y + h / 2 - (len(lines) - 1) * 19 / 2 + 5
    text(x + w / 2, top, lines, color=color, bold_first=bold_first)


def lane(x, y, w, h, name, detail, fill="#f1f5f9", stroke="#64748b", color="#334155"):
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" '
               f'stroke="{stroke}" stroke-width="1.5"/>')
    out.append(f'<text x="{x + 16}" y="{y + 22}" font-size="13" fill="{color}">'
               f'<tspan font-weight="700" letter-spacing="0.8">{name}</tspan>'
               f'<tspan fill="{MUTED}">  {detail}</tspan></text>')


def arrow(points, label=None, at=None, anchor="middle"):
    d = " ".join(f"{'M' if i == 0 else 'L'} {x} {y}" for i, (x, y) in enumerate(points))
    out.append(f'<path d="{d}" fill="none" stroke="{LINE}" stroke-width="2" marker-end="url(#head)"/>')
    if label:
        lx, ly = at
        for i, line in enumerate(label):
            out.append(f'<text x="{lx}" y="{ly + i * 16}" font-size="12.5" fill="{LINE}" text-anchor="{anchor}" '
                       f'paint-order="stroke" stroke="#fff" stroke-width="5">{line}</text>')


AI = dict(fill="#eef2ff", stroke="#4338ca", color="#312e81")       # Gemini calls
CODE = dict(fill="#f0fdf4", stroke="#15803d", color="#14532d")     # plain code

# Input: what the scraper hands over
box(20, 230, 230, 190, ["Scraped by Playwright", "article: title, paragraph,", "infobox fields",
                        "lead image (file)", "image labels: caption,", "alt text, file name"], fill="#f8fafc")

# Lanes
lane(330, 20, 690, 160, "STANDARD MODE", "· default · 1 Gemini call")
lane(330, 205, 690, 210, "SUPER MODE", "· API value \"thorough\" · 2 Gemini calls (≈ 2× time and cost)")
lane(330, 440, 690, 160, "LABEL CHECK", "· plain code, no AI · Super mode only", fill="#f7fdf9", stroke="#15803d",
     color="#14532d")

box(470, 60, 410, 100, ["Gemini: verdict", "sees: image + article", "returns: description · reason · PASS/FAIL"], **AI)

box(360, 248, 290, 140, ["Call 1: blind description", "sees: image only", "no article, no labels",
                         "returns: description"], **AI)
box(700, 248, 300, 140, ["Call 2: verdict", "sees: image + article", "+ the blind description",
                         "returns: reason · PASS/FAIL"], **AI)
arrow([(650, 318), (696, 318)])

box(360, 480, 640, 100, ["Does the caption, alt text or file name contain a title word?",
                         "agrees · unclear (no title word) · no labels"], **CODE)

# Fan-out from the input (orthogonal)
arrow([(250, 325), (290, 325), (290, 110), (466, 110)], ["standard"], (298, 101), anchor="start")
arrow([(250, 325), (290, 325), (290, 318), (356, 318)], ["super"], (298, 309), anchor="start")
arrow([(250, 325), (290, 325), (290, 530), (356, 530)], ["super"], (298, 521), anchor="start")

# Result
box(1110, 150, 320, 380, ["Result", "", "Verdict = Gemini PASS / FAIL", "(the labels never change it)", "",
                          "Super mode: Needs review when", "FAIL and labels agree, or",
                          "PASS and labels unclear", "", "Standard: the original report,", "no labels, no review flag",
                          "", "Saved: verification_mode;", "super adds label_check, needs_review"],
    fill="#fffbeb", stroke="#a16207", color="#713f12")
arrow([(880, 110), (1060, 110), (1060, 250), (1106, 250)], ["verdict"], (1060, 102))
arrow([(1000, 318), (1106, 318)], ["verdict"], (1053, 310))
arrow([(1000, 530), (1060, 530), (1060, 430), (1106, 430)])

text(20, 632, ["Blue: Gemini calls.  Green: plain code.  Arrows show what each step passes on; "
               "the arrow labels are the mode.  Mode: the Super mode switch on the Verify page; the API gets \"mode\": \"standard\" or \"thorough\"."],
     size=13, color=MUTED, anchor="start", bold_first=False)

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
       f'font-family="{FONT}">'
       f'<defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" '
       f'orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{LINE}"/></marker></defs>'
       f'<rect width="100%" height="100%" fill="#ffffff"/>' + "".join(out) + "</svg>")
(HERE / "verification.svg").write_text(svg, encoding="utf-8")

if __name__ == "__main__":
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(device_scale_factor=2, viewport={"width": W, "height": H})
        page.set_content(f'<html><body style="margin:0;background:#fff">{svg}</body></html>')
        page.locator("svg").screenshot(path=str(HERE / "verification.png"))
        browser.close()
