"""Generate docs/images/mode-standard.png and mode-super.png (and .svg).

Run from the project root:  python docs/images/modes.py
One simple pipeline diagram per verification mode (spec SRCH-15), matching
app/services/pipeline_service.py. Arrows show what each step receives.
Uses the Playwright Chromium the app already installs.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
INK, MUTED, LINE = "#0f172a", "#475569", "#334155"
FONT = "Noto Sans, Liberation Sans, Arial, sans-serif"
AI = dict(fill="#eef2ff", stroke="#4338ca", color="#312e81")      # Gemini call
CODE = dict(fill="#f0fdf4", stroke="#15803d", color="#14532d")    # plain code
INPUT = dict(fill="#f8fafc", stroke=LINE, color=INK)
OUTPUT = dict(fill="#fffbeb", stroke="#a16207", color="#713f12")


class Canvas:
    def __init__(self):
        self.out: list[str] = []

    def text(self, x, y, lines, size=14, color=INK, anchor="middle", bold_first=True):
        for i, line in enumerate(lines):
            weight = 700 if (i == 0 and bold_first) else 400
            fill = color if (i == 0 or not bold_first) else MUTED
            s = size if i == 0 else size - 1.5
            self.out.append(f'<text x="{x}" y="{y + i * (size + 5)}" font-size="{s}" font-weight="{weight}" '
                            f'fill="{fill}" text-anchor="{anchor}">{line}</text>')

    def box(self, x, y, w, h, lines, fill, stroke, color):
        self.out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="{fill}" '
                        f'stroke="{stroke}" stroke-width="1.5"/>')
        self.text(x + w / 2, y + h / 2 - (len(lines) - 1) * 19 / 2 + 5, lines, color=color)

    def arrow(self, points, label=None, at=None, anchor="middle"):
        d = " ".join(f"{'M' if i == 0 else 'L'} {x} {y}" for i, (x, y) in enumerate(points))
        self.out.append(f'<path d="{d}" fill="none" stroke="{LINE}" stroke-width="2" marker-end="url(#head)"/>')
        if label:
            self.out.append(f'<text x="{at[0]}" y="{at[1]}" font-size="12.5" fill="{LINE}" text-anchor="{anchor}" '
                            f'paint-order="stroke" stroke="#fff" stroke-width="5">{label}</text>')

    def heading(self, name, detail):
        self.out.append(f'<text x="24" y="30" font-size="14" fill="#334155"><tspan font-weight="700" '
                        f'letter-spacing="0.8">{name}</tspan><tspan fill="{MUTED}">  {detail}</tspan></text>')

    def svg(self, w, h):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
                f'font-family="{FONT}"><defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" '
                f'markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" '
                f'fill="{LINE}"/></marker></defs><rect width="100%" height="100%" fill="#ffffff"/>'
                + "".join(self.out) + "</svg>")


def standard() -> str:
    c = Canvas()
    c.heading("STANDARD MODE", "· default (switch off) · 1 Gemini call · the task's requirement")
    c.box(30, 70, 210, 60, ["Image", "lead image from Wikipedia"], **INPUT)
    c.box(30, 190, 210, 70, ["Scraped details", "title · first paragraph", "infobox fields"], **INPUT)
    c.box(390, 105, 240, 120, ["Gemini call", "sees: image + details", "describe the image, then", "decide if it shows the subject"], **AI)
    c.arrow([(240, 100), (310, 100), (310, 145), (386, 145)])
    c.arrow([(240, 225), (310, 225), (310, 185), (386, 185)])
    for y, lines in ((55, ["Description", "what the image shows"]), (135, ["Reason", "why it does or doesn't match"]),
                     (215, ["PASS / FAIL", "the verdict"])):
        c.box(760, y, 220, 60, lines, **OUTPUT)
    c.arrow([(630, 165), (700, 165), (700, 85), (756, 85)])
    c.arrow([(700, 165), (756, 165)])
    c.arrow([(700, 165), (700, 245), (756, 245)])
    c.text(24, 312, ["Blue: Gemini call.  Yellow: what the report shows.  One request: image and details together "
                     "(Task 1, step 5)."], size=13, color=MUTED, anchor="start", bold_first=False)
    return c.svg(1010, 330)


def super_mode() -> str:
    c = Canvas()
    c.heading("SUPER MODE", "· switch on · API value \"thorough\" · 2 Gemini calls + label check")
    c.box(30, 70, 210, 60, ["Image", "lead image from Wikipedia"], **INPUT)
    c.box(30, 250, 210, 70, ["Scraped details", "title · first paragraph", "infobox fields"], **INPUT)
    c.box(30, 390, 210, 70, ["Image labels", "caption · alt text", "file name"], **INPUT)

    c.box(330, 60, 230, 80, ["Gemini call 1", "sees: image ONLY"], **AI)
    c.box(650, 60, 230, 80, ["Blind description", "what the image shows", "(shown in the report)"], **OUTPUT)
    c.box(650, 225, 230, 120, ["Gemini call 2", "sees: image + details", "+ blind description", "decides the match"], **AI)
    c.box(650, 395, 230, 80, ["Label check (code, no AI)", "do the labels contain", "a title word?"], **CODE)

    c.box(980, 205, 200, 60, ["Reason", "why it does or doesn't match"], **OUTPUT)
    c.box(980, 290, 200, 60, ["PASS / FAIL", "the verdict (never changed)"], **OUTPUT)
    c.box(980, 395, 200, 80, ["Needs review", "only if the label check", "and the verdict disagree"], **OUTPUT)

    c.arrow([(240, 100), (326, 100)])                                   # image -> call 1
    c.arrow([(285, 100), (285, 255), (646, 255)], "image", (300, 249), anchor="start")  # image -> call 2
    c.arrow([(240, 285), (646, 285)], "details", (440, 279))            # details -> call 2
    c.arrow([(560, 100), (646, 100)])                                   # call 1 -> blind description
    c.arrow([(765, 140), (765, 221)], "blind description", (775, 186), anchor="start")
    c.arrow([(240, 425), (646, 425)], "labels + title", (440, 419))     # labels -> label check
    c.arrow([(880, 285), (930, 285), (930, 235), (976, 235)])           # call 2 -> reason
    c.arrow([(930, 285), (930, 320), (976, 320)])                       # call 2 -> verdict
    c.arrow([(880, 435), (976, 435)])                                   # label check -> review
    c.arrow([(1080, 350), (1080, 391)])                                 # verdict -> review
    c.text(24, 512, ["Blue: Gemini calls.  Green: plain code.  Yellow: what the report shows.  "
                     "The labels never reach Gemini, so the label check stays independent."],
           size=13, color=MUTED, anchor="start", bold_first=False)
    return c.svg(1210, 530)


if __name__ == "__main__":
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, svg in (("mode-standard", standard()), ("mode-super", super_mode())):
            (HERE / f"{name}.svg").write_text(svg, encoding="utf-8")
            page = browser.new_page(device_scale_factor=2)
            page.set_content(f'<html><body style="margin:0;background:#fff">{svg}</body></html>')
            page.locator("svg").screenshot(path=str(HERE / f"{name}.png"))
        browser.close()
