"""
generate.py - builds dark_mode.svg and light_mode.svg (neofetch-style profile card).

Run locally:   python generate.py
In Actions:    GITHUB_TOKEN + GITHUB_REPOSITORY_OWNER are set automatically, so the
               "GitHub Stats" block gets live numbers. Without a token it shows "--".

Edit the INFO list below to change what the card says. Everything is plain
monospace text, so alignment is just character counting: each row is padded
with dots to exactly WIDTH characters.
"""
import json
import os
import urllib.request
from html import escape

# ── layout ────────────────────────────────────────────────────────────────
WIDTH = 60                      # characters per info row
ART_FONT, ART_LINE = 8, 8.8      # px (tools/make_ascii.py uses the same values)
ART_CHAR_W = 4.8                 # px per art column; textLength pins every row to this grid
INFO_FONT, INFO_LINE = 15, 21   # px
SVG_W, SVG_H = 1176, 640
ART_X, ART_Y = 36, 76
INFO_X, INFO_Y = 612, 78
FONT = "ConsolasFallback, Consolas, 'JetBrains Mono', Menlo, 'Courier New', monospace"

HANDLE = "farras@github"

# ("section", title) | ("kv", key, value) | ("status",) | ("stats",)
INFO = [
    ("header",),
    ("status",),
    ("kv", "OS", "Farras Raihan Akbar Firmansyah"),
    ("kv", "Host", "BINUS University, Jakarta, ID"),
    ("kv", "Kernel", "Computer Engineering Student"),
    ("kv", "Environment", "VSCode, Windows Terminal"),
    ("kv", "Tools", "Git, Arduino, Node.js"),
    ("kv", "Languages.Programming", "C, C++, C#, Python, JS, Java, PHP"),
    ("kv", "Languages.Web", "React, Next.js, Web3.js"),
    ("kv", "Languages.Real", "Indonesian, English"),
    ("kv", "Design.UI", "Figma, Canva"),
    ("kv", "Design.Graphics", "Photoshop, Illustrator, Affinity"),
    ("kv", "Design.Motion", "After Effects, Premiere Pro"),
    ("kv", "Focus", "AI Engineering, Web, Embedded"),
    ("kv", "Hobbies", "Designing, Tinkering, Gaming"),
    ("section", "Contact"),
    ("kv", "Timezone", "WIB (UTC+7)"),
    ("kv", "Email", "farras.raf12@gmail.com"),
    ("kv", "LinkedIn", "in/farras-raihan-akbar-b9515b333"),
    ("kv", "Instagram", "@farras.rhnaf"),
    ("kv", "Discord", "discord.com/users/611947839626412033"),
    ("section", "GitHub Stats"),
    ("stats",),
    ("rule",),
    ("comment", "// Design is not just what it looks like and feels like."),
    ("comment", "// Design is how it works. - Steve Jobs", True),
]

THEMES = {
    "dark": dict(
        bg="#0d1117", card="#161b22", border="#30363d", bar="#1c2128",
        text="#e6edf3", key="#d2a8ff", dot="#484f58", value="#a5d6ff",
        num="#7ee787", comment="#8b949e", ok="#3fb950",
        panel="#0d1117", panel_border="#30363d",
    ),
    "light": dict(
        bg="#ffffff", card="#f6f8fa", border="#d0d7de", bar="#eaeef2",
        text="#1f2328", key="#8250df", dot="#afb8c1", value="#0a3069",
        num="#116329", comment="#6e7781", ok="#1a7f37",
        panel="#0d1117", panel_border="#d0d7de",
    ),
}


# ── GitHub stats ──────────────────────────────────────────────────────────
def _get(url, token, data=None):
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-card",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_stats():
    token = os.getenv("GITHUB_TOKEN")
    user = os.getenv("GITHUB_REPOSITORY_OWNER") or os.getenv("GH_USER")
    blank = dict(repos="--", contrib="--", stars="--", commits="--", followers="--")
    if not (token and user):
        return blank
    try:
        api = "https://api.github.com"
        u = _get(f"{api}/users/{user}", token)
        stars, page = 0, 1
        while True:  # paginate owned public repos to sum stars
            repos = _get(f"{api}/users/{user}/repos?per_page=100&type=owner&page={page}", token)
            stars += sum(r["stargazers_count"] for r in repos)
            if len(repos) < 100:
                break
            page += 1
        commits = _get(f"{api}/search/commits?q=author:{user}&per_page=1", token)["total_count"]
        q = {"query": f'{{user(login:"{user}"){{repositoriesContributedTo('
                      f'contributionTypes:[COMMIT,PULL_REQUEST,REPOSITORY]){{totalCount}}}}}}'}
        gql = _get(f"{api}/graphql", token, json.dumps(q).encode())
        contrib = gql["data"]["user"]["repositoriesContributedTo"]["totalCount"]
        return dict(repos=u["public_repos"], contrib=contrib, stars=stars,
                    commits=f"{commits:,}", followers=u["followers"])
    except Exception as e:  # never break the card because the API hiccuped
        print("stats fetch failed:", e)
        return blank


# ── row builders: each returns a list of (text, css_class) segments ───────
def dots(n):
    return [(" " + "." * max(n - 2, 1) + " ", "d")]


def key_segs(key):
    segs = []
    for i, part in enumerate(key.split(".")):
        if i:
            segs.append((".", "t"))
        segs.append((part, "k"))
    return segs


def kv(key, value, vcls="v"):
    used = 2 + len(key) + 1 + len(value)        # ". " + key + ":" + value
    return [(". ", "d"), *key_segs(key), (":", "t"), *dots(WIDTH - used), (value, vcls)]


def rule_line(title=None):
    if title is None:
        return [("—" * (WIDTH - 3) + "-—-", "d")]
    head = f"- {title} "
    return [("- ", "t"), (title, "t"), (" " + "—" * (WIDTH - len(head) - 3) + "-—-", "d")]


def status_line():
    value = "● Running (stable)"
    used = 2 + len("Status") + 1 + len(value)
    return [(". ", "d"), ("Status", "k"), (":", "t"), *dots(WIDTH - used),
            ("●", "ok pulse"), (" Running (stable)", "v")]


def stats_lines(s):
    # row 1:  . Repos: .... 12 {Contributed: 3} | Stars: ........ 4
    left = [(". ", "d"), ("Repos", "k"), (":", "t")]
    r_val = [(str(s["repos"]), "n"), (" {", "t"), ("Contributed", "k"), (": ", "t"),
             (str(s["contrib"]), "n"), ("}", "t")]
    right = [(" | ", "t"), ("Stars", "k"), (":", "t")]
    st = [(str(s["stars"]), "n")]
    row1 = _two_col(left, r_val, right, st, 34)
    left2 = [(". ", "d"), ("Commits", "k"), (":", "t")]
    right2 = [(" | ", "t"), ("Followers", "k"), (":", "t")]
    row2 = _two_col(left2, [(str(s["commits"]), "n")], right2, [(str(s["followers"]), "n")], 34)
    return [row1, row2]


def _two_col(lk, lv, rk, rv, split):
    ln = lambda segs: sum(len(t) for t, _ in segs)
    a = lk + dots(split - ln(lk) - ln(lv)) + lv
    b = rk + dots(WIDTH - split - ln(rk) - ln(rv)) + rv
    return a + b


def build_rows(stats):
    rows = []
    for item in INFO:
        kind = item[0]
        if kind == "header":
            rows.append([(HANDLE, "h"), (" " + "—" * (WIDTH - len(HANDLE) - 4) + "-—-", "d")])
        elif kind == "status":
            rows.append(status_line())
        elif kind == "kv":
            rows.append(kv(item[1], item[2]))
        elif kind == "section":
            rows.append(rule_line(item[1]))
        elif kind == "rule":
            rows.append(rule_line())
        elif kind == "stats":
            rows.extend(stats_lines(stats))
        elif kind == "comment":
            text = item[1]
            segs = [(" " * (WIDTH - len(text) - (2 if len(item) > 2 else 0)) + text, "c")]
            if len(item) > 2:
                segs.append((" ▋", "cursor"))
            rows.append(segs)
    return rows


def color_runs(line, cols):
    """Group consecutive same-colored chars into one <tspan>. Spaces join whatever
    run they're in (their color is invisible), which keeps the SVG small."""
    runs, cur, buf = [], None, ""
    for ch, k in zip(line, cols):
        k = int(k, 16)
        if ch != " " and k != cur and buf:
            runs.append((cur, buf)); buf = ""
        if ch != " " or cur is None:
            cur = k if ch != " " else (cur if cur is not None else k)
        buf += ch
    if buf:
        runs.append((cur, buf))
    return "".join(f'<tspan class="p{k}">{escape(t)}</tspan>' for k, t in runs)


# ── SVG ───────────────────────────────────────────────────────────────────
def render(theme, art, rows):
    c = THEMES[theme]
    art_css = " ".join(f".p{i}{{fill:{col}}}" for i, col in enumerate(art["palette"]))
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_W}" height="{SVG_H}" '
           f'viewBox="0 0 {SVG_W} {SVG_H}" font-family="{FONT}">']
    out.append(f"""<style>
  .h{{fill:{c['text']};font-weight:700}} .t{{fill:{c['text']}}} .k{{fill:{c['key']}}}
  .d{{fill:{c['dot']}}} .v{{fill:{c['value']}}} .n{{fill:{c['num']}}}
  .c{{fill:{c['comment']};font-style:italic}} .ok{{fill:{c['ok']}}}
  .cursor{{fill:{c['key']};animation:blink 1.1s steps(1) infinite}}
  .pulse{{animation:pulse 2.4s ease-in-out infinite}}
  .art{{animation:fadein 1.6s ease-out both}}
  {art_css}
  @keyframes blink{{50%{{opacity:0}}}}
  @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.35}}}}
  @keyframes fadein{{from{{opacity:0}}to{{opacity:1}}}}
</style>""")
    # window chrome
    out.append(f'<rect width="{SVG_W}" height="{SVG_H}" rx="14" fill="{c["card"]}" stroke="{c["border"]}"/>')
    out.append(f'<path d="M0.5 14 a13.5 13.5 0 0 1 13.5 -13.5 H{SVG_W-14} a13.5 13.5 0 0 1 13.5 13.5 V38 H0.5Z" fill="{c["bar"]}"/>')
    out.append(f'<line x1="0" y1="38.5" x2="{SVG_W}" y2="38.5" stroke="{c["border"]}"/>')
    for i, col in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        out.append(f'<circle cx="{22+i*20}" cy="19" r="6" fill="{col}"/>')
    out.append(f'<text x="{SVG_W/2}" y="24" text-anchor="middle" font-size="13" class="d">'
               f'farras@binus: ~/README.md — neofetch</text>')

    # ascii art inside a dark "image well" (same in both themes, so colors stay true)
    n_rows, n_cols = len(art["chars"]), len(art["chars"][0])
    art_w = n_cols * ART_CHAR_W
    px, py = ART_X - 12, ART_Y - ART_FONT - 10
    out.append(f'<rect x="{px}" y="{py}" width="{art_w + 24}" height="{n_rows * ART_LINE + 22}" '
               f'rx="10" fill="{c["panel"]}" stroke="{c["panel_border"]}"/>')
    out.append(f'<g class="art" font-size="{ART_FONT}">')
    for i, (line, cols) in enumerate(zip(art["chars"], art["colors"])):
        out.append(f'<text x="{ART_X}" y="{ART_Y + i * ART_LINE:.1f}" textLength="{art_w}" '
                   f'lengthAdjust="spacing" xml:space="preserve">{color_runs(line, cols)}</text>')
    out.append("</g>")

    # info panel
    out.append(f'<text x="{INFO_X}" y="{INFO_Y}" font-size="{INFO_FONT}" xml:space="preserve">')
    for i, segs in enumerate(rows):
        y = INFO_Y + i * INFO_LINE
        inner = "".join(f'<tspan class="{cls}">{escape(t)}</tspan>' for t, cls in segs)
        out.append(f'<tspan x="{INFO_X}" y="{y}">{inner}</tspan>')
    out.append("</text></svg>")
    return "\n".join(out)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "art.json")) as f:
        art = json.load(f)
    rows = build_rows(fetch_stats())
    for r in rows:  # sanity check: every info row must be exactly WIDTH chars
        n = sum(len(t) for t, _ in r)
        if n != WIDTH:
            print(f"warning: row is {n} chars (want {WIDTH}):", "".join(t for t, _ in r))
    for theme in THEMES:
        with open(os.path.join(here, f"{theme}_mode.svg"), "w") as f:
            f.write(render(theme, art, rows))
    print("wrote dark_mode.svg, light_mode.svg")


if __name__ == "__main__":
    main()
