"""Generate docs/images/usecase.svg and usecase.png (UML use case diagram).

Run from the project root:  python docs/images/usecase.py
Use cases match the API endpoints in README section 3 and the React pages.
Uses the Playwright Chromium the app already installs.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
W, H = 1260, 960
INK, MUTED, LINE = "#0f172a", "#475569", "#334155"
FONT = "Noto Sans, Liberation Sans, Arial, sans-serif"
USER = ("#eef2ff", "#4338ca")    # user use cases
ADMIN = ("#fdf4ff", "#a21caf")   # admin only
INNER = ("#f0fdfa", "#0f766e")   # included / extending
out: list[str] = []

AX, BX, RX, RY = 430, 838, 155, 27   # use case columns and ellipse radii


def actor(x, y, name):
    """Stick figure; (x, y) is the hip."""
    s = f'stroke="{LINE}" stroke-width="2" fill="none"'
    out.append(f'<circle cx="{x}" cy="{y - 44}" r="13" fill="#fff" stroke="{LINE}" stroke-width="2"/>'
               f'<path d="M {x} {y - 31} V {y} M {x - 22} {y - 20} H {x + 22} '
               f'M {x} {y} L {x - 16} {y + 30} M {x} {y} L {x + 16} {y + 30}" {s}/>'
               f'<text x="{x}" y="{y + 54}" font-size="17" font-weight="700" fill="{INK}" '
               f'text-anchor="middle">{name}</text>')


def system_actor(x, y, name):
    out.append(f'<rect x="{x}" y="{y - 30}" width="170" height="60" rx="6" fill="#fff7ed" stroke="#c2410c" '
               f'stroke-width="1.5"/><text x="{x + 85}" y="{y - 6}" font-size="13" fill="#9a3412" '
               f'text-anchor="middle">«system»</text><text x="{x + 85}" y="{y + 15}" font-size="16" '
               f'font-weight="700" fill="#7c2d12" text-anchor="middle">{name}</text>')


def case(cx, cy, name, colors):
    fill, stroke = colors
    out.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{RX}" ry="{RY}" fill="{fill}" stroke="{stroke}" '
               f'stroke-width="1.5"/><text x="{cx}" y="{cy + 6}" font-size="17" font-weight="500" fill="{INK}" '
               f'text-anchor="middle">{name}</text>')


def line(x1, y1, x2, y2):
    out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{LINE}" stroke-width="1.4"/>')


def dep(x1, y1, x2, y2, label, lx, ly):
    """Dashed dependency with an open arrowhead and a stereotype label."""
    out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{LINE}" stroke-width="1.4" '
               f'stroke-dasharray="6 4" marker-end="url(#open)"/>'
               f'<text x="{lx}" y="{ly}" font-size="13.5" fill="{LINE}" text-anchor="middle" paint-order="stroke" '
               f'stroke="#fff" stroke-width="5">{label}</text>')


# System boundary
out.append('<rect x="230" y="30" width="780" height="900" rx="10" fill="#fcfcfd" stroke="#64748b" stroke-width="1.6"/>')
out.append(f'<text x="250" y="58" font-size="16" font-weight="700" fill="{INK}">VerifyLens</text>')

# Actors
UX, UY = 110, 360
AXA, AYA = 110, 790
actor(UX, UY, "User")
actor(AXA, AYA, "Admin")
# Generalization: Admin is a User (hollow triangle at User)
out.append(f'<line x1="{AXA}" y1="{AYA - 58}" x2="{UX}" y2="{UY + 76}" stroke="{LINE}" stroke-width="1.6" '
           f'marker-end="url(#tri)"/>')
out.append(f'<text x="{UX + 10}" y="{(UY + AYA) / 2 + 20}" font-size="13.5" fill="{MUTED}">inherits all</text>'
           f'<text x="{UX + 10}" y="{(UY + AYA) / 2 + 36}" font-size="13.5" fill="{MUTED}">User use cases</text>')

# User use cases
user_cases = [
    (110, "Sign in"), (170, "Sign out"), (230, "Change own password"), (290, "Check system status"),
    (360, "Verify a Wikipedia topic"), (430, "View and download report"), (490, "View search history"),
    (550, "Delete a search record"), (620, "Reset forgotten password"),
]
for cy, name in user_cases:
    case(AX, cy, name, USER)
    line(UX + 26, UY - 20, AX - RX, cy)

# Admin use cases
admin_cases = [(700, "Manage user accounts"), (760, "Set temporary password"), (820, "View all users' searches"),
               (880, "View admin overview")]
for cy, name in admin_cases:
    case(AX, cy, name, ADMIN)
    line(AXA + 26, AYA - 20, AX - RX, cy)

# Included and extending use cases
case(BX, 290, "Scrape article and image", INNER)
case(BX, 360, "Verify image with Gemini", INNER)
case(BX, 440, "Super mode check", INNER)
case(BX, 620, "Send reset email", INNER)
dep(AX + 125, 346, BX - 125, 304, "«include»", 620, 314)
dep(AX + RX, 360, BX - RX - 2, 360, "«include»", 634, 352)
dep(BX - 135, 427, AX + 135, 373, "«extend»", 652, 400)
dep(AX + RX, 620, BX - RX - 2, 620, "«include»", 634, 612)

# External systems
SX = 1060
system_actor(SX, 290, "Wikipedia")
system_actor(SX, 360, "Google Gemini")
system_actor(SX, 620, "Mail server")
line(BX + RX, 290, SX, 290)
line(BX + RX, 360, SX, 360)
line(BX + RX, 620, SX, 620)

# Notes
out.append(f'<text x="{BX - RX}" y="490" font-size="13.5" fill="{MUTED}">Super mode: second Gemini call and</text>'
           f'<text x="{BX - RX}" y="506" font-size="13.5" fill="{MUTED}">label check, chosen with a switch</text>'
           f'<text x="{BX - RX}" y="668" font-size="13.5" fill="{MUTED}">Optional, off by default</text>')

# Legend
ly = H - 10
lx = 20
for name, (fill, stroke) in (("User use case", USER), ("Admin only", ADMIN), ("Included or extending", INNER)):
    out.append(f'<ellipse cx="{lx + 14}" cy="{ly - 5}" rx="14" ry="8" fill="{fill}" stroke="{stroke}"/>'
               f'<text x="{lx + 36}" y="{ly}" font-size="14" fill="{MUTED}">{name}</text>')
    lx += 36 + len(name) * 7 + 30

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
       f'font-family="{FONT}"><defs>'
       f'<marker id="open" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" '
       f'orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10" fill="none" stroke="{LINE}" stroke-width="1.5"/></marker>'
       f'<marker id="tri" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="14" markerHeight="14" '
       f'markerUnits="userSpaceOnUse" orient="auto"><path d="M0 0 L12 6 L0 12 z" fill="#fff" stroke="{LINE}" '
       f'stroke-width="1.2"/></marker></defs>'
       f'<rect width="100%" height="100%" fill="#ffffff"/>' + "".join(out) + "</svg>")
(HERE / "usecase.svg").write_text(svg, encoding="utf-8")

if __name__ == "__main__":
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(device_scale_factor=2, viewport={"width": W, "height": H})
        page.set_content(f'<html><body style="margin:0;background:#fff">{svg}</body></html>')
        page.locator("svg").screenshot(path=str(HERE / "usecase.png"))
        browser.close()
