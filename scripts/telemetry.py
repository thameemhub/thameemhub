"""Render the profile's public contribution calendar and non-fork repository activity."""
import json
import math
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree

OUTPUT = Path(__file__).resolve().parents[1] / "assets" / "generated"
OWNER = os.environ.get("GITHUB_REPOSITORY_OWNER", "thameemhub")
THEMES = {
    "dark": ("#08090D", "#F4F6FC", "#A4ACBA", "#242736", "#00D9FF",
             ["#20232E", "#711635", "#AC1743", "#E6224C", "#FF6484"]),
    "light": ("#F7F7FA", "#13131C", "#505361", "#DADBE2", "#006F82",
              ["#DFE0E7", "#FCC1CD", "#F97996", "#CE2858", "#97082F"]),
}


def query(document, **variables):
    body = json.dumps({"query": document, "variables": variables}).encode()
    request = Request("https://api.github.com/graphql", data=body, headers={
        "Authorization": "Bearer " + os.environ["GH_TOKEN"],
        "Content-Type": "application/json", "User-Agent": "thameemhub-profile",
    })
    with urlopen(request, timeout=30) as response:
        result = json.load(response)
    if result.get("errors"):
        raise RuntimeError(result["errors"])
    return result["data"]["user"]


def fetch_snapshot():
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=364)).date().isoformat()
    result = query("""
      query($owner:String!, $start:DateTime!, $end:DateTime!) {
        user(login:$owner) { contributionsCollection(from:$start,to:$end) {
          contributionCalendar { weeks { contributionDays { date contributionCount contributionLevel } } }
        } }
      }""", owner=OWNER, start=start + "T00:00:00Z", end=now.isoformat())
    weeks = result["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [day for week in weeks for day in week["contributionDays"]
            if start <= day["date"] <= now.date().isoformat()]
    if len(days) != 365 or any(
        day["date"] != (now.date() - timedelta(days=364 - i)).isoformat()
        for i, day in enumerate(days)
    ):
        raise ValueError("GitHub returned an incomplete contribution calendar")

    repositories = []
    cursor = None
    while True:
        result = query("""
          query($owner:String!, $cursor:String) {
            user(login:$owner) { repositories(first:50,after:$cursor,privacy:PUBLIC,
                ownerAffiliations:OWNER,isFork:false) { pageInfo { hasNextPage endCursor }
              nodes { name pushedAt stargazerCount languages(first:100,orderBy:{field:SIZE,direction:DESC}) {
                pageInfo { hasNextPage } edges { size node { name } }
              } }
            } }
          }""", owner=OWNER, cursor=cursor)["repositories"]
        repositories.extend(result["nodes"])
        if not result["pageInfo"]["hasNextPage"]:
            break
        cursor = result["pageInfo"]["endCursor"]
    return days, repositories


def label(x, y, value, size, color, mono=False, bold=False):
    family = "Consolas,monospace" if mono else "Arial,sans-serif"
    return (f'<text x="{x}" y="{y}" fill="{color}" font-family="{family}" '
            f'font-weight="{700 if bold else 400}" font-size="{size}">{escape(str(value))}</text>')


def svg(width, height, title, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img"><title>{escape(title)}</title>\n'
            + "\n".join(body) + "\n</svg>\n")


def streaks(counts):
    current = longest = 0
    for count in counts:
        current = current + 1 if count else 0
        longest = max(current, longest)
    if not counts[-1]:
        current = 0
        for count in reversed(counts[:-1]):
            if not count:
                break
            current += 1
    return current, longest


def calendar_cells(days):
    start = datetime.fromisoformat(days[0]["date"])
    offset = (start.weekday() + 1) % 7
    levels = ["NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"]
    return [(n // 7, n % 7, day["contributionCount"], levels.index(day["contributionLevel"]))
            for n, day in enumerate(days, offset)]


def city(days, theme):
    bg, fg, muted, line, accent, colors = theme
    counts = [d["contributionCount"] for d in days]
    cells = calendar_cells(days)
    body = [f'<rect width="900" height="302" rx="13" fill="{bg}"/>',
            label(30, 36, "CONTRIBUTION TOPOGRAPHY", 13, accent, True),
            label(28, 79, f"{sum(counts):,} contributions", 35, fg, bold=True),
            label(30, 105, f'{days[0]["date"]}  /  {days[-1]["date"]}', 15, muted, True)]
    maximum = max(1, max(counts))
    for col, row, count, level in cells:
        x, y = 97 + col * 14.6 - row * 9.2, 157 + col * 1.4 + row * 5.4
        height = 2 + 83 * math.log1p(count) / math.log1p(maximum)
        top = y - height
        def pts(*coords):
            return " ".join(f"{a:.1f},{b:.1f}" for a, b in coords)
        a, b = (x, top), (x + 13.6, top + 1.3)
        c, d = (x + 5, top + 6.4), (x - 8.6, top + 5.1)
        body.append(f'<g fill="{colors[level]}" stroke="{line}" stroke-width=".45">'
                    f'<polygon points="{pts(d,c,(c[0],y+6.4),(d[0],y+5.1))}" fill-opacity=".63"/>'
                    f'<polygon points="{pts(c,b,(b[0],y+1.3),(c[0],y+6.4))}" fill-opacity=".85"/>'
                    f'<polygon points="{pts(a,b,c,d)}"/></g>')
    body.append(label(30, 284, "One tower per day  /  height follows contribution count on a logarithmic scale", 13, muted))
    return svg(900, 302, "Daily GitHub contributions shown as an isometric city", body)


def snake(days, theme):
    bg, fg, muted, _, accent, colors = theme
    cells = calendar_cells(days)
    body = [f'<rect width="900" height="203" rx="12" fill="{bg}"/>',
            label(30, 35, "CONTRIBUTION SNAKE", 14, fg, True, True),
            label(30, 183, "Sunday to Saturday by column  /  oldest week on the left", 14, muted)]
    route = []
    for col, row, count, level in sorted(cells, key=lambda d: (d[0], d[1] if d[0] % 2 == 0 else -d[1])):
        x, y = 30 + col * 16, 54 + row * 15
        body.append(f'<rect x="{x}" y="{y}" width="12" height="11" rx="2" fill="{colors[level]}"/>')
        route.append(f"{x+6},{y+5.5}")
    path = "M" + " ".join(route)
    # Dash units use pathLength. Each moving dash follows the same grid path.
    body += ['<style>@keyframes slither{to{stroke-dashoffset:-100}}'
             '.snake{animation:slither 50s linear infinite}'
             '@media(prefers-reduced-motion:reduce){.snake{animation:none}}</style>']
    for length, offset, ink, width in [(1.55, 0, "#FF1744", 8), (.16, 0, accent, 5)]:
        body.append(f'<path d="{path}" pathLength="100" fill="none" stroke="{ink}" stroke-width="{width}" '
                    f'stroke-linecap="round" class="snake" stroke-dasharray="{length} {100-length}" '
                    f'stroke-dashoffset="{offset}"/>')
    return svg(900, 203, "Animated snake traversing the actual daily contribution grid", body)


def statistics(days, repos, theme):
    bg, fg, muted, line, accent, _ = theme
    counts = [d["contributionCount"] for d in days]
    current, longest = streaks(counts)
    langs = Counter()
    for repo in repos:
        if repo["languages"]["pageInfo"]["hasNextPage"]:
            raise ValueError("Language listing is incomplete for " + repo["name"])
        for edge in repo["languages"]["edges"]:
            langs[edge["node"]["name"]] += edge["size"]
    recent = sorted((r for r in repos if r["name"].lower() != OWNER.lower() and r["pushedAt"]),
                    key=lambda r: r["pushedAt"], reverse=True)[:2]
    body = [f'<rect width="600" height="385" rx="12" fill="{bg}"/>',
            label(22, 32, "PUBLIC REPOSITORIES", 15, accent, True, True),
            label(338, 32, days[-1]["date"] + " UTC", 14, muted, True)]
    for i, (value, key) in enumerate([(len(repos), "Owned repos"), (sum(r["stargazerCount"] for r in repos), "Stars"),
                                      (current, "Streak / days"), (longest, "Best / days")]):
        x = 22+i*144
        body.extend([label(x, 83, value, 36, fg, bold=True), label(x, 108, key, 16, muted)])
    body.extend([f'<path d="M22 129H578" stroke="{line}"/>', label(22, 157, "LANGUAGES BY CODE SIZE", 14, accent, True)])
    for i, (name, size) in enumerate(langs.most_common(4)):
        percent = 100 * size / sum(langs.values())
        y = 187 + 24*i
        body.extend([label(22,y,name,16,fg), f'<rect x="222" y="{y-10}" width="259" height="6" rx="3" fill="{line}"/>',
                     f'<rect x="222" y="{y-10}" width="{2.59*percent:.2f}" height="6" rx="3" fill="#E42B55"/>',
                     label(500,y,f"{percent:.1f}%",15,muted,True)])
    body.append(label(22, 308, "RECENTLY PUSHED", 14, accent, True))
    for i, repo in enumerate(recent):
        name = repo["name"]
        if len(name) > 39:
            name = name[:38] + "…"
        body.extend([label(22, 338+i*24, name, 15, fg, True),
                     label(473, 338+i*24, repo["pushedAt"][:10], 14, muted, True)])
    return svg(600, 385, "Repository statistics, calendar streaks, languages and recent pushes", body)


def main():
    days, repos = fetch_snapshot()
    assets = {}
    for name, theme in THEMES.items():
        assets[f"city-{name}.svg"] = city(days, theme)
        assets[f"snake-{name}.svg"] = snake(days, theme)
        assets[f"statistics-{name}.svg"] = statistics(days, repos, theme)
    for content in assets.values():
        ElementTree.fromstring(content)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for file, content in assets.items():
        (OUTPUT / file).write_text(content, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
