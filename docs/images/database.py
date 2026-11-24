"""Generate docs/images/database.svg and database.png (ER diagram).

Run from the project root:  python docs/images/database.py
Matches app/db/models.py (plus the indexes in app/db/migrations.py).
Crow's foot notation. Uses the Playwright Chromium the app already installs.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
W, H = 1420, 670
INK, MUTED, LINE = "#0f172a", "#475569", "#334155"
FONT = "Noto Sans, Liberation Sans, Arial, sans-serif"
MONO = "DejaVu Sans Mono, Liberation Mono, Consolas, monospace"
HEAD, ROW = 38, 26
TW = 400  # table width
BADGE = {"PK": ("#fef3c7", "#a16207"), "FK": ("#e0e7ff", "#4338ca"),
         "UK": ("#dcfce7", "#15803d"), "IX": ("#f1f5f9", "#475569")}
out: list[str] = []

# (key, field, type, nullable)
USER = [("PK", "id", "INTEGER", False), ("UK", "username", "VARCHAR", False),
        ("", "hashed_password", "VARCHAR", False), ("", "role", "VARCHAR", False),
        ("", "is_active", "BOOLEAN", False), ("", "created_at", "DATETIME", False),
        ("", "full_name", "VARCHAR", True), ("", "token_version", "INTEGER", False),
        ("", "must_change_password", "BOOLEAN", False), ("UK", "email", "VARCHAR", True)]
SEARCH = [("PK", "id", "INTEGER", False), ("IX", "query", "VARCHAR", False),
          ("", "article_title", "VARCHAR", True), ("", "source_url", "VARCHAR", True),
          ("", "image_url", "VARCHAR", True), ("", "fields_json", "VARCHAR", True),
          ("", "status", "VARCHAR", False), ("", "matches", "BOOLEAN", True),
          ("", "report_markdown", "VARCHAR", True), ("", "error_message", "VARCHAR", True),
          ("", "created_at", "DATETIME", False), ("FK", "user_id", "INTEGER", True),
          ("", "verification_mode", "VARCHAR", True), ("", "label_check", "VARCHAR", True),
          ("", "needs_review", "BOOLEAN", True)]
REFRESH = [("PK", "id", "INTEGER", False), ("FK", "user_id", "INTEGER", False),
           ("UK", "token_hash", "VARCHAR", False), ("IX", "family_id", "VARCHAR", False),
           ("", "token_version", "INTEGER", False), ("", "created_at", "DATETIME", False),
           ("", "expires_at", "DATETIME", False), ("", "family_expires_at", "DATETIME", False),
           ("", "replaced_at", "DATETIME", True), ("", "revoked_at", "DATETIME", True)]
RESET = [("PK", "id", "INTEGER", False), ("FK", "user_id", "INTEGER", False),
         ("UK", "token_hash", "VARCHAR", False), ("", "created_at", "DATETIME", False),
         ("", "expires_at", "DATETIME", False), ("", "used_at", "DATETIME", True),
         ("", "requested_ip", "VARCHAR", True)]


def row_y(y, i):
    """Vertical centre of row i in a table whose top is y."""
    return y + HEAD + i * ROW + ROW / 2


def table(x, y, name, purpose, rows):
    h = HEAD + len(rows) * ROW
    out.append(f'<rect x="{x}" y="{y}" width="{TW}" height="{h}" rx="6" fill="#fff" stroke="{LINE}" stroke-width="1.5"/>')
    out.append(f'<path d="M {x} {y + HEAD} V {y + 6} Q {x} {y} {x + 6} {y} H {x + TW - 6} Q {x + TW} {y} {x + TW} {y + 6} '
               f'V {y + HEAD} Z" fill="#1e293b"/>')
    out.append(f'<text x="{x + 14}" y="{y + 24}" font-size="15" font-weight="700" fill="#fff">{name}'
               f'<tspan font-size="12.5" font-weight="400" fill="#cbd5e1">  {purpose}</tspan></text>')
    for i, (key, field, typ, nullable) in enumerate(rows):
        top = y + HEAD + i * ROW
        cy = top + ROW / 2 + 4.5
        if i % 2:
            out.append(f'<rect x="{x + 1}" y="{top}" width="{TW - 2}" height="{ROW}" fill="#f8fafc"/>')
        if i:
            out.append(f'<line x1="{x}" y1="{top}" x2="{x + TW}" y2="{top}" stroke="#e2e8f0"/>')
        if key:
            fill, stroke = BADGE[key]
            out.append(f'<rect x="{x + 10}" y="{top + 5}" width="30" height="16" rx="3" fill="{fill}" stroke="{stroke}"/>'
                       f'<text x="{x + 25}" y="{top + 17}" font-size="10.5" font-weight="700" fill="{stroke}" '
                       f'text-anchor="middle">{key}</text>')
        weight = 700 if key == "PK" else 400
        out.append(f'<text x="{x + 52}" y="{cy}" font-size="13.5" font-family="{MONO}" font-weight="{weight}" '
                   f'fill="{INK}">{field}</text>')
        out.append(f'<text x="{x + 262}" y="{cy}" font-size="12" font-family="{MONO}" fill="{MUTED}">{typ}</text>')
        if nullable:
            out.append(f'<text x="{x + TW - 12}" y="{cy}" font-size="11.5" fill="#94a3b8" text-anchor="end">null</text>')
    return h


def path(points):
    d = " ".join(f"{'M' if i == 0 else 'L'} {px} {py}" for i, (px, py) in enumerate(points))
    out.append(f'<path d="{d}" fill="none" stroke="{LINE}" stroke-width="1.6"/>')


def end(x, y, d, kind):
    """Crow's foot end at the table edge (x, y); d = +1 if the table is to the right.

    kind: "one" (exactly one), "zero_one" (zero or one), "many" (zero or many).
    """
    s = f'stroke="{LINE}" stroke-width="1.6" fill="none"'
    if kind == "many":
        out.append(f'<path d="M {x - 14 * d} {y} L {x} {y - 8} M {x - 14 * d} {y} L {x} {y + 8}" {s}/>')
        out.append(f'<circle cx="{x - 22 * d}" cy="{y}" r="5" fill="#fff" stroke="{LINE}" stroke-width="1.6"/>')
    elif kind == "one":
        for off in (8, 14):
            out.append(f'<line x1="{x - off * d}" y1="{y - 7}" x2="{x - off * d}" y2="{y + 7}" {s}/>')
    else:  # zero or one
        out.append(f'<line x1="{x - 8 * d}" y1="{y - 7}" x2="{x - 8 * d}" y2="{y + 7}" {s}/>')
        out.append(f'<circle cx="{x - 20 * d}" cy="{y}" r="5" fill="#fff" stroke="{LINE}" stroke-width="1.6"/>')


def label(x, y, lines, anchor="middle"):
    for i, line in enumerate(lines):
        out.append(f'<text x="{x}" y="{y + i * 16}" font-size="12.5" fill="{LINE}" text-anchor="{anchor}" '
                   f'paint-order="stroke" stroke="#fff" stroke-width="5">{line}</text>')


out.append(f'<text x="30" y="34" font-size="14" fill="#334155"><tspan font-weight="700" letter-spacing="0.8">'
           f'DATABASE</tspan><tspan fill="{MUTED}">  SQLite (SQLModel), data/search_history.db, 4 tables</tspan></text>')

SX, UX, RX = 30, 510, 990
TOP = 60
table(SX, TOP, "searchrecord", "one search", SEARCH)
table(UX, TOP, "user", "account + role", USER)
table(RX, TOP, "refreshtoken", "stay signed in", REFRESH)
RESET_Y = 400
table(RX, RESET_Y, "passwordresettoken", "reset link", RESET)

uid = row_y(TOP, 0)  # user.id
# user 1 -- 0..N searchrecord (user_id may be NULL: unlinked when the user is deleted)
s_uid = row_y(TOP, 11)
path([(UX, uid), (470, uid), (470, s_uid), (SX + TW, s_uid)])
end(UX, uid, 1, "zero_one")
end(SX + TW, s_uid, -1, "many")
label(470, 250, ["owns", "1:N"])
# user 1 -- 0..N refreshtoken / passwordresettoken (user_id required)
r_uid, p_uid = row_y(TOP, 1), row_y(RESET_Y, 1)
path([(UX + TW, uid), (950, uid), (950, r_uid), (RX, r_uid)])
path([(950, r_uid), (950, p_uid), (RX, p_uid)])
end(UX + TW, uid, -1, "one")
end(RX, r_uid, 1, "many")
end(RX, p_uid, 1, "many")
label(950, 250, ["has", "1:N"])

# Constraints and values (under the user table)
NX, NY, NW = UX, 400, TW
notes = [
    ("role", "CHECK IN ('admin', 'user')"),
    ("status", "PENDING → SUCCESS or ERROR"),
    ("verification_mode", "standard, thorough (Super)"),
    ("label_check", "agrees, unclear, no_labels"),
    ("token_hash", "SHA-256 only, never the token"),
    ("hashed_password", "Argon2 hash, no plaintext"),
    ("Delete user", "searches kept, user_id → NULL;"),
    ("", "its tokens are deleted"),
]
nh = 40 + len(notes) * 22
out.append(f'<rect x="{NX}" y="{NY}" width="{NW}" height="{nh}" rx="6" fill="#fffbeb" stroke="#a16207" stroke-width="1.5"/>')
out.append(f'<text x="{NX + 14}" y="{NY + 25}" font-size="14" font-weight="700" fill="#713f12">Constraints and values</text>')
for i, (k, v) in enumerate(notes):
    ty = NY + 50 + i * 22
    out.append(f'<text x="{NX + 14}" y="{ty}" font-size="12.5" font-family="{MONO}" fill="#713f12">{k}</text>'
               f'<text x="{NX + 168}" y="{ty}" font-size="12.5" fill="#713f12">{v}</text>')

# Legend
ly = H - 22
items = [("PK", "primary key"), ("FK", "foreign key → user.id (indexed)"), ("UK", "unique"), ("IX", "indexed")]
for (key, text), lx in zip(items, (30, 170, 430, 540)):
    fill, stroke = BADGE[key]
    out.append(f'<rect x="{lx}" y="{ly - 12}" width="30" height="16" rx="3" fill="{fill}" stroke="{stroke}"/>'
               f'<text x="{lx + 15}" y="{ly}" font-size="10.5" font-weight="700" fill="{stroke}" text-anchor="middle">{key}</text>'
               f'<text x="{lx + 38}" y="{ly}" font-size="12.5" fill="{MUTED}">{text}</text>')
out.append(f'<text x="660" y="{ly}" font-size="12.5" fill="{MUTED}">null = optional (NULL allowed)</text>')
# Crow's foot key: draw the real symbols
for sx, kind, text in ((910, "one", "exactly one"), (1060, "zero_one", "zero or one"), (1215, "many", "zero or many")):
    path([(sx, ly - 4), (sx + 44, ly - 4)])
    end(sx + 44, ly - 4, 1, kind)
    out.append(f'<text x="{sx + 52}" y="{ly}" font-size="12.5" fill="{MUTED}">{text}</text>')

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">'
       f'<rect width="100%" height="100%" fill="#ffffff"/>' + "".join(out) + "</svg>")
(HERE / "database.svg").write_text(svg, encoding="utf-8")

if __name__ == "__main__":
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(device_scale_factor=2, viewport={"width": W, "height": H})
        page.set_content(f'<html><body style="margin:0;background:#fff">{svg}</body></html>')
        page.locator("svg").screenshot(path=str(HERE / "database.png"))
        browser.close()
