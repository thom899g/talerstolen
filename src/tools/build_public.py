#!/usr/bin/env python3
"""Bygger den selvstændige, offentlige udgave af Talerstolen i mappen public/.

Brug:  python3 tools/build_public.py [guide|alt] [udmappe]
  guide = kun partiguiden (I dag, Partier, Sammenlign, Debatter, Træn). Videoværksted, DF-argumentbank,
          karriereplan og afsnittet "parti X og Dansk Folkeparti" tages helt ud af data, ikke kun ud af menuen.
  alt   = hele siden.
Den offentlige side læser live/*.json i stedet for Claude-databasen og har ingen Claude-funktioner.
"""
import json, os, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
scope = sys.argv[1] if len(sys.argv) > 1 else "guide"
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "public")
guide = scope != "alt"

page = open(os.path.join(ROOT, "site", "index.html"), encoding="utf-8").read()
head, body = page.split('<header class="top">', 1)
body = '<header class="top">' + body
head = head.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', "").replace("<title>Talerstolen</title>\n", "")

DESC = "De 12 danske partier forklaret ned i detaljen: mærkesager, holdninger emne for emne, aktuelle debatter og hvem der stemte hvad i Folketinget."
ICON = "data:image/svg+xml," + ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><rect width='24' height='24' rx='5' fill='%2312161C'/>"
                                "<path d='M7 10h10l-1.4 9H8.4L7 10Z' fill='white'/><path d='M5.6 10h12.8' stroke='white' stroke-width='1.9' stroke-linecap='round'/>"
                                "<path d='M12 10V6.2l2.4-1.3' stroke='white' stroke-width='1.4' stroke-linecap='round' fill='none'/><circle cx='15' cy='4.7' r='1.2' fill='white'/></svg>")
site = {"video": not guide, "career": not guide, "bank": not guide}
doc = f"""<!doctype html>
<html lang="da">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Talerstolen – de danske partier forklaret</title>
<meta name="description" content="{DESC}">
<meta property="og:title" content="Talerstolen">
<meta property="og:description" content="{DESC}">
<meta property="og:type" content="website">
<meta property="og:locale" content="da_DK">
<meta name="theme-color" content="#F3F4F7" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0E1115" media="(prefers-color-scheme: dark)">
<link rel="icon" href="{ICON}">
<style>:root{{color-scheme:light;padding:env(safe-area-inset-top,0px) 0 env(safe-area-inset-bottom,0px)}}body{{margin:0;font:14px system-ui,sans-serif}}img{{max-width:100%}}[hidden]{{display:none!important}}</style>
{head.strip()}
</head>
<body>
<noscript><p style="padding:24px;font:16px system-ui,sans-serif">Talerstolen kræver JavaScript for at vise partierne og de aktuelle debatter.</p></noscript>
<script>window.TS_SITE = {json.dumps(site)};</script>
{body.strip()}
</body>
</html>
"""
os.makedirs(os.path.join(OUT, "live"), exist_ok=True)
open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(doc)
open(os.path.join(OUT, ".nojekyll"), "w").write("")

# data.js: fjern alt, der ikke skal være offentligt i guide-udgaven
raw = open(os.path.join(ROOT, "site", "data.js"), encoding="utf-8").read()
ts = json.loads(raw[len("window.TS = "):].rstrip().rstrip(";").replace("<\\/", "</"))
if guide:
    for k in ("dfExtra", "career", "hooks", "moves", "checklist", "format", "plan"):
        ts.pop(k, None)
    for p in ts["parties"]:
        p.pop("vsDF", None)
open(os.path.join(OUT, "data.js"), "w", encoding="utf-8").write(
    "window.TS = " + json.dumps(ts, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + ";\n")

names = ["meta", "ft", "national", "partydebates", "news"] + ([] if guide else ["videos"])
for n in names:
    src = os.path.join(ROOT, "live", n + ".json")
    if os.path.exists(src):
        shutil.copyfile(src, os.path.join(OUT, "live", n + ".json"))
stale = os.path.join(OUT, "live", "videos.json")
if guide and os.path.exists(stale):
    os.remove(stale)
size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(OUT) for f in fs if ".git" not in dp)
print("public/ bygget (%s): %d KB i alt | live: %s" % ("kun partiguiden" if guide else "hele siden", size // 1024, ", ".join(names)))
