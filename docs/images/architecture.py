"""Generate docs/images/architecture.svg and architecture.png.

Run from the project root:  python docs/images/architecture.py
Every box and arrow was checked against the code (imports and call sites)
on 2026-11-24. Arrows point from caller to callee; the reply returns on the
same connection. Uses the Playwright Chromium the app already installs.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
W, H = 1500, 1140  # drawing starts at y = 40 (viewBox offset)
INK, MUTED, LINE = "#0f172a", "#475569", "#334155"
FONT = "Noto Sans, Liberation Sans, Arial, sans-serif"
# (accent, tint) per layer
CLIENT = ("#4f46e5", "#f5f7ff")
API = ("#7c3aed", "#faf7ff")
SERVICE = ("#0d9488", "#f3fbfa")
DATA = ("#2563eb", "#f4f8ff")
EXT = ("#ea580c", "#fff8f3")
TOOL = ("#64748b", "#f8fafc")
out: list[str] = []


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def layer(x, y, w, h, name, detail, colors, dash=None):
    accent, tint = colors
    d = f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{tint}" stroke="{accent}" '
               f'stroke-opacity="0.45" stroke-width="1.5"{d}/>')
    out.append(f'<text x="{x + 18}" y="{y + 25}" font-size="13" fill="{accent}"><tspan font-weight="700" '
               f'letter-spacing="1">{name}</tspan><tspan fill="{MUTED}">   {esc(detail)}</tspan></text>')


def card(x, y, w, h, title, lines, colors, center=False):
    """White card; title bold, detail lines muted. colors is unused (kept for call-site clarity)."""
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="#fff" stroke="#e2e8f0" '
               f'stroke-width="1" filter="url(#shadow)"/>')
    n = 1 + len(lines)
    top = y + h / 2 - (n - 1) * 18 / 2 + 5
    tx, anchor = (x + w / 2, "middle") if center else (x + 16, "start")
    out.append(f'<text x="{tx}" y="{top}" font-size="14.5" font-weight="700" fill="{INK}" '
               f'text-anchor="{anchor}">{esc(title)}</text>')
    for i, line in enumerate(lines):
        out.append(f'<text x="{tx}" y="{top + (i + 1) * 18}" font-size="12.5" fill="{MUTED}" '
                   f'text-anchor="{anchor}">{esc(line)}</text>')


def arrow(points, dash=None):
    d = " ".join(f"{'M' if i == 0 else 'L'} {px} {py}" for i, (px, py) in enumerate(points))
    da = f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<path d="{d}" fill="none" stroke="{LINE}" stroke-width="1.8" marker-end="url(#head)"{da}/>')


def pill(x, y, label, anchor="start"):
    """Arrow label in a small rounded white box; (x, y) is the left (or centre) of the pill."""
    w = len(label) * 6.1 + 22
    left = x - w / 2 if anchor == "middle" else x
    out.append(f'<rect x="{left}" y="{y - 11}" width="{w}" height="22" rx="11" fill="#fff" stroke="#cbd5e1"/>'
               f'<text x="{left + w / 2}" y="{y + 4.5}" font-size="12" fill="{LINE}" '
               f'text-anchor="middle">{esc(label)}</text>')


CX = 520  # centre line of the main column

# Client
layer(20, 56, 1000, 122, "CLIENT", "Browser", CLIENT)
card(40, 94, 470, 66, "React app", ["React 19, Vite 7"], CLIENT)
card(530, 94, 470, 66, "Session state", ["access token in memory, refresh token in HttpOnly cookie"], CLIENT)
arrow([(CX, 178), (CX, 230)])
pill(CX + 14, 194, "HTTPS, JSON, Bearer token")
pill(CX + 14, 222, "refresh cookie: /api/v1/auth only")

# Reverse proxy
card(20, 234, 1000, 58, "Reverse proxy (nginx or Caddy), TLS", ["dev: Vite server on :5173"], TOOL, center=True)
arrow([(CX, 292), (CX, 340)])
pill(CX + 14, 316, "HTTP 127.0.0.1:8000")

# Server boundary
out.append('<rect x="20" y="344" width="1000" height="636" rx="14" fill="none" stroke="#1e3a8a" '
           'stroke-width="1.6" stroke-dasharray="8 6"/>')
out.append(f'<text x="38" y="370" font-size="13" fill="#1e3a8a"><tspan font-weight="700" letter-spacing="1">SERVER'
           f'</tspan><tspan fill="{MUTED}">   Python 3.12, one Uvicorn process, Docker (not yet built)</tspan></text>')

# API layer
layer(60, 384, 940, 132, "API LAYER", "FastAPI, Pydantic", API)
card(76, 424, 200, 74, "Static frontend", ["built React app"], API)
card(292, 424, 250, 74, "REST routes", ["/api/v1"], API)
card(558, 424, 260, 74, "Security", ["JWT, Argon2, roles, CSRF"], API)
card(834, 424, 150, 74, "Rate limiter", ["in memory"], API)
arrow([(CX, 516), (CX, 562)])
pill(CX + 14, 539, "calls")

# Service layer
layer(60, 566, 940, 260, "SERVICE LAYER", "app/services", SERVICE)
card(76, 604, 908, 40, "Search pipeline: scrape, verify, label check, report", [], SERVICE, center=True)
xs = (76, 307, 538, 769)
for x in xs:
    arrow([(x + 107, 644), (x + 107, 662)])
card(xs[0], 666, 215, 64, "Wikipedia scraper", ["Playwright"], SERVICE)
card(xs[1], 666, 215, 64, "Gemini verifier", ["1 call, Super mode 2"], SERVICE)
card(xs[2], 666, 215, 64, "Label check", ["Super mode only"], SERVICE)
card(xs[3], 666, 215, 64, "Report", ["Markdown"], SERVICE)
card(xs[0], 742, 215, 64, "Refresh tokens", ["issue, rotate, revoke"], SERVICE)
card(xs[1], 742, 215, 64, "Password reset", ["email link"], SERVICE)
card(xs[2], 742, 215, 64, "Mail", ["smtplib"], SERVICE)
card(xs[3], 742, 215, 64, "Health check", ["cached 60 s"], SERVICE)
arrow([(CX, 826), (CX, 870)])
pill(CX + 14, 848, "calls")

# Data layer
layer(60, 874, 940, 92, "DATA LAYER", "SQLModel, app/infra/db", DATA)
card(76, 906, 908, 44, "Sessions, models, repositories, migrations", [], DATA, center=True)

# SQLite (file on a persistent volume)
arrow([(CX, 966), (CX, 1032)])
pill(CX + 14, 1004, "SQL")
cx, top, rx, ry, height = CX, 1050, 250, 16, 70
out.append(f'<path d="M {cx - rx} {top} A {rx} {ry} 0 0 0 {cx + rx} {top} L {cx + rx} {top + height} '
           f'A {rx} {ry} 0 0 1 {cx - rx} {top + height} Z" fill="#eff6ff" stroke="{DATA[0]}" stroke-width="1.6" '
           f'filter="url(#shadow)"/>')
out.append(f'<ellipse cx="{cx}" cy="{top}" rx="{rx}" ry="{ry}" fill="#dbeafe" stroke="{DATA[0]}" stroke-width="1.6"/>')
out.append(f'<text x="{cx}" y="{top + 38}" font-size="14.5" font-weight="700" fill="#1e3a8a" text-anchor="middle">'
           f'SQLite (WAL)</text>'
           f'<text x="{cx}" y="{top + 57}" font-size="12.5" fill="{MUTED}" text-anchor="middle">'
           f'data/search_history.db</text>')

# CLI scripts
card(820, 1046, 270, 80, "CLI scripts", ["bootstrap_admin, reset_password", "backup_db"], TOOL)
arrow([(820, 1086), (cx + rx + 4, 1086)])

# External services
layer(1060, 566, 420, 324, "EXTERNAL SERVICES", "", EXT)
card(1080, 604, 380, 80, "Wikipedia", ["HTTPS"], EXT)
card(1080, 696, 380, 80, "Google Gemini API", ["HTTPS"], EXT)
card(1080, 788, 380, 84, "SMTP mail server", ["STARTTLS :587, optional"], EXT)
arrow([(1000, 644), (1076, 644)])
arrow([(1000, 736), (1076, 736)])
arrow([(1000, 800), (1030, 800), (1030, 830), (1076, 830)])

# Legend
ly = H + 40 - 22
lx = 20
for name, (accent, _) in (("Client", CLIENT), ("API", API), ("Services", SERVICE), ("Data", DATA),
                          ("External", EXT), ("Infrastructure", TOOL)):
    out.append(f'<rect x="{lx}" y="{ly - 11}" width="12" height="12" rx="3" fill="{accent}"/>'
               f'<text x="{lx + 18}" y="{ly}" font-size="12.5" fill="{MUTED}">{name}</text>')
    lx += 18 + len(name) * 7.2 + 22
out.append(f'<text x="{lx + 8}" y="{ly}" font-size="12.5" fill="{MUTED}">Arrows go from caller to callee. '
           f'Dashed line: deployment boundary.</text>')

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 40 {W} {H}" '
       f'font-family="{FONT}"><defs>'
       f'<marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7.5" markerHeight="7.5" '
       f'orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{LINE}"/></marker>'
       f'<filter id="shadow" x="-5%" y="-10%" width="110%" height="130%"><feDropShadow dx="0" dy="1.5" '
       f'stdDeviation="1.6" flood-color="#0f172a" flood-opacity="0.10"/></filter></defs>'
       f'<rect y="40" width="{W}" height="{H}" fill="#ffffff"/>' + "".join(out) + "</svg>")
(HERE / "architecture.svg").write_text(svg, encoding="utf-8")

if __name__ == "__main__":
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(device_scale_factor=2, viewport={"width": W, "height": H})
        page.set_content(f'<html><body style="margin:0;background:#fff">{svg}</body></html>')
        page.locator("svg").screenshot(path=str(HERE / "architecture.png"))
        browser.close()
