"""Generate docs/images/architecture.svg and architecture.png.

Run from the project root:  python docs/images/architecture.py
Every box and arrow was checked against the code (imports and call sites)
on 2026-11-24. Arrows point from caller to callee; the reply returns on the
same connection. Uses the Playwright Chromium the app already installs.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
W, H = 1450, 1080
INK, MUTED, LINE = "#0f172a", "#475569", "#334155"
FONT = "Noto Sans, Liberation Sans, Arial, sans-serif"
out: list[str] = []


def text(x, y, lines, size=14, weight=400, color=INK, anchor="middle"):
    for i, line in enumerate(lines):
        w = 700 if (i == 0 and weight == 700) else 400
        c = color if (i == 0 or weight != 700) else MUTED
        s = size if i == 0 else size - 1.5
        out.append(f'<text x="{x}" y="{y + i * (size + 5)}" font-size="{s}" font-weight="{w}" '
                   f'fill="{c}" text-anchor="{anchor}">{line}</text>')


def box(x, y, w, h, lines, fill="#ffffff", stroke=LINE, color=INK, dash=None, radius=6, title=True):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" '
               f'stroke="{stroke}" stroke-width="1.5"{d}/>')
    n = len(lines)
    top = y + h / 2 - (n - 1) * 19 / 2 + 5
    text(x + w / 2, top, lines, weight=700 if title else 400, color=color)


def layer(x, y, w, h, name, detail, fill="#f1f5f9", stroke="#64748b", color="#334155", dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" '
               f'stroke="{stroke}" stroke-width="1.5"{d}/>')
    out.append(f'<text x="{x + 16}" y="{y + 22}" font-size="13" fill="{color}">'
               f'<tspan font-weight="700" letter-spacing="0.8">{name}</tspan>'
               f'<tspan fill="{MUTED}">  {detail}</tspan></text>')


def arrow(points, label=None, at=None, anchor="start", dash=None):
    d = " ".join(f"{'M' if i == 0 else 'L'} {x} {y}" for i, (x, y) in enumerate(points))
    da = f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<path d="{d}" fill="none" stroke="{LINE}" stroke-width="2" marker-end="url(#head)"{da}/>')
    if label:
        lx, ly = at
        for i, line in enumerate(label):
            out.append(f'<text x="{lx}" y="{ly + i * 16}" font-size="12.5" fill="{LINE}" '
                       f'text-anchor="{anchor}" paint-order="stroke" stroke="#fff" stroke-width="5">{line}</text>')


CX = 490  # centre line of the main column

# Client
layer(20, 20, 940, 110, "CLIENT", "· Browser")
box(40, 52, 440, 62, ["React app", "React 19 · Vite 7 · react-markdown"])
box(500, 52, 440, 62, ["Session state", "access token in memory · refresh token in HttpOnly cookie"])
arrow([(CX, 130), (CX, 176)], ["HTTPS · JSON · Bearer access token", "refresh cookie sent only to /api/v1/auth"], (CX + 14, 148))

# Reverse proxy
box(20, 180, 940, 52, ["Reverse proxy (nginx / Caddy) · TLS termination — production",
                       "development: Vite dev server :5173 forwards /api"], fill="#f8fafc")
arrow([(CX, 232), (CX, 286)], ["HTTP · 127.0.0.1:8000"], (CX + 14, 262))

# Server boundary
layer(20, 290, 940, 600, "SERVER", "· Python 3.12 · one Uvicorn process · Docker container (written, not yet built)",
      fill="#fafcff", stroke="#1e3a8a", color="#1e3a8a", dash="7 5")

# API layer
layer(60, 326, 860, 116, "API LAYER", "· FastAPI · Pydantic   (app/api, app/dto, security/)")
box(76, 360, 190, 66, ["Static frontend", "built React files", "app/frontend.py"])
box(278, 360, 220, 66, ["REST routes /api/v1", "auth · users · search · history", "admin · password reset · health"])
box(510, 360, 230, 66, ["Security", "PyJWT (HS256) · Argon2 (pwdlib)", "password policy · roles · CSRF"])
box(752, 360, 152, 66, ["Rate limiter", "in-memory counters", "(per process)"])

arrow([(CX, 442), (CX, 494)], ["calls"], (CX + 14, 472))

# Service layer
layer(60, 498, 860, 190, "SERVICE LAYER", "· app/services")
box(76, 532, 160, 68, ["Search pipeline", "scrape → verify", "→ report"])
box(248, 532, 190, 68, ["Wikipedia scraper", "Playwright", "headless Chromium"])
box(450, 532, 170, 68, ["Gemini verifier", "google-genai"])
box(632, 532, 120, 68, ["Report", "Markdown"])
box(764, 532, 140, 68, ["Health check", "DB, Wikipedia,", "Gemini (cached 60 s)"])
box(76, 610, 270, 62, ["Refresh tokens", "issue · rotate · revoke"])
box(358, 610, 270, 62, ["Password reset", "one-time email links"])
box(640, 610, 264, 62, ["Mail", "smtplib"])

arrow([(CX, 688), (CX, 742)], ["calls"], (CX + 14, 718))

# Routes that query the database themselves (not through a service)
arrow([(60, 400), (40, 400), (40, 790), (58, 790)])
out.append(f'<text x="34" y="595" font-size="12.5" fill="{LINE}" text-anchor="middle" '
           f'transform="rotate(-90 34 595)" paint-order="stroke" stroke="#fafcff" stroke-width="6">'
           f'routes also query directly (users, admin, auth, history)</text>')

# Data layer
layer(60, 746, 860, 104, "DATA LAYER", "· SQLModel / SQLAlchemy   (app/db)")
box(76, 780, 828, 54, ["Engine &amp; sessions · table models · SearchRepository · additive migrations at startup"],
    title=False)

# SQLite (file on a persistent volume)
arrow([(CX, 850), (CX, 932)], ["SQL read / write"], (CX + 14, 916))
cx, top, rx, ry, height = CX, 952, 230, 16, 72
out.append(f'<path d="M {cx - rx} {top} A {rx} {ry} 0 0 0 {cx + rx} {top} L {cx + rx} {top + height} '
           f'A {rx} {ry} 0 0 1 {cx - rx} {top + height} Z" fill="#eff6ff" stroke="#1d4ed8" stroke-width="1.5"/>')
out.append(f'<ellipse cx="{cx}" cy="{top}" rx="{rx}" ry="{ry}" fill="#eff6ff" stroke="#1d4ed8" stroke-width="1.5"/>')
text(cx, top + 34, ["SQLite (WAL mode) · data/search_history.db",
                    "user · searchrecord · refreshtoken · passwordresettoken"], weight=700, color="#1e3a8a")

# CLI scripts
box(790, 950, 260, 78, ["CLI scripts (separate processes)", "bootstrap_admin · reset_password", "backup_db"],
    fill="#f8fafc")
arrow([(790, 989), (cx + rx + 4, 989)])

# External services
layer(1040, 452, 390, 290, "EXTERNAL SERVICES", "", fill="#fffbf5", stroke="#c2410c", color="#9a3412")
ext = dict(fill="#fff7ed", stroke="#c2410c", color="#7c2d12")
box(1060, 486, 350, 76, ["Wikipedia  (HTTPS)", "article page + image: scraper", "reachability probe: health check"], **ext)
box(1060, 572, 350, 76, ["Google Gemini API  (HTTPS)", "image verdict: verifier", "model check: health check"], **ext)
box(1060, 658, 350, 76, ["SMTP mail server  (SMTP + STARTTLS :587)", "password-reset emails: mail",
                         "optional, off by default"], **ext)
arrow([(920, 524), (1056, 524)])
arrow([(920, 610), (1056, 610)])
arrow([(920, 678), (990, 678), (990, 696), (1056, 696)])

# Legend
text(20, 1062, ["Arrows point from caller to callee; each reply returns on the same connection.  "
                "Dashed border: deployment boundary."], size=13, color=MUTED, anchor="start")

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
       f'font-family="{FONT}">'
       f'<defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" '
       f'orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{LINE}"/></marker></defs>'
       f'<rect width="100%" height="100%" fill="#ffffff"/>' + "".join(out) + "</svg>")
(HERE / "architecture.svg").write_text(svg, encoding="utf-8")

if __name__ == "__main__":
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(device_scale_factor=2, viewport={"width": W, "height": H})
        page.set_content(f'<html><body style="margin:0;background:#fff">{svg}</body></html>')
        page.locator("svg").screenshot(path=str(HERE / "architecture.png"))
        browser.close()
