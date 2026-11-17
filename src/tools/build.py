#!/usr/bin/env python3
"""Samler research-filerne til site/data.js (fast viden) og live/*.json (det der ligger i sidens database)."""
import json, os, re, sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(ROOT, *p)
load = lambda *p: json.load(open(D(*p), encoding="utf-8"))
IDS = ["s", "sf", "rv", "m", "v", "la", "k", "df", "dd", "el", "alt", "bp"]
BANNED = re.compile(r"\b[Jj]eg \b|verificer|bør tjekkes|søgeuddrag|søgeopsummering|SCHEMA|hukommelsen|kunne ikke|ikke fundet|[Ii]kke bekræftet|ikke undersøgt|foreløbigt skøn|år ikke vist|ifølge Wikipedia|\(Wikipedia\)")
TOPICS = None
warn = []
# id -> (navn, kaldenavn i løbende tekst, forkortelse)
NAMES = {"s": ("Socialdemokratiet", "Socialdemokratiet", "S"), "sf": ("Socialistisk Folkeparti", "SF", "SF"), "rv": ("Radikale Venstre", "Radikale", "RV"),
         "m": ("Moderaterne", "Moderaterne", "M"), "v": ("Venstre", "Venstre", "V"), "la": ("Liberal Alliance", "Liberal Alliance", "LA"),
         "k": ("Det Konservative Folkeparti", "Konservative", "K"), "df": ("Dansk Folkeparti", "DF", "DF"), "dd": ("Danmarksdemokraterne", "Danmarksdemokraterne", "DD"),
         "el": ("Enhedslisten", "Enhedslisten", "EL"), "alt": ("Alternativet", "Alternativet", "ALT"), "bp": ("Borgernes Parti", "Borgernes Parti", "BP")}
# Afstemninger fra 27. aug.-1. okt. 2026 hører til samlingen 2025-26 (2. samling), kode 20252. Numrene er genbrugt i 2026-27.
OLDKW = {"B3": ["bededag"], "B5": ["asbest", "kursusordning"], "B6": ["koranlov"], "B8": ["formildende", "unge alder"], "B9": ["håndtryk"],
         "B11": ["bønnekald", "bøn"], "B13": ["svømning", "svømme"], "B16": ["statsrevisor"], "B18": ["forvaltningsdomstol"], "B26": ["ombudsmand"],
         "B27": ["indkomstmodtager"], "L5": ["gødskning", "næringsstof", "kvælstof"], "L6": ["reparation"], "L8": ["rykkergebyr"], "L9": ["hvidvask"],
         "L10": ["solcelle"], "L11": ["spiral", "antikonception"], "L12": ["tobak", "nikotin"], "L13": ["sanktion"], "L15": ["migration", "asyl"],
         "L16": ["beløbsordning"], "L17": ["udvis", "hjemrejse", "repatriering"], "L19": ["id-kort", "byggeplads"], "L21": ["studieophold"]}
# Ens skala på tværs af partier (rækkefølge: el sf alt s rv m k v la dd df bp). En forenklet redaktionel vurdering.
SORDER = ["el", "sf", "alt", "s", "rv", "m", "k", "v", "la", "dd", "df", "bp"]
SCORES = {"udlaendinge": "131423444555", "oekonomi": "122334445334", "arbejdsmarked": "122244445223", "velfaerd": "112233345224",
          "sundhed": "112223345224", "klima": "121323334445", "natur_landbrug": "121323344544", "eu": "422211223454",
          "forsvar": "232545555433", "ret": "131423544555", "bolig": "122233445334", "uddannelse": "112323445334"}
URLRE = re.compile(r"^https://www\.ft\.dk/samling/20261/(lovforslag|beslutningsforslag)/([LB]\d+)/index\.htm$", re.I)


def fix_urls(node, anc=()):
    """Skift samlingskode til 20252, når linket peger på en af de gamle afstemninger (afgøres ud fra teksten omkring linket)."""
    if isinstance(node, dict):
        own = " ".join(v for v in node.values() if isinstance(v, str))
        u = node.get("url")
        m = URLRE.match(u) if isinstance(u, str) else None
        if m and m.group(2).upper() in OLDKW:
            ctx = (own + " " + " ".join(anc[-2:])).lower()
            if any(k in ctx for k in OLDKW[m.group(2).upper()]):
                node["url"] = u.replace("/20261/", "/20252/")
        for v in node.values():
            fix_urls(v, anc + (own,))
    elif isinstance(node, list):
        for v in node:
            fix_urls(v, anc)


def clean(x, path=""):
    """Fjern null/tomme felter rekursivt og saml advarsler om arbejdsnoter."""
    if isinstance(x, dict):
        out = {}
        for k, v in x.items():
            c = clean(v, path + "." + k)
            if c is None or c == "" or c == [] or c == {}:
                continue
            out[k] = c
        return out
    if isinstance(x, list):
        return [c for c in (clean(v, path + "[]") for v in x) if c not in (None, "", [], {})]
    if isinstance(x, str):
        s = re.sub(r"\s+", " ", x).strip()
        if BANNED.search(s) and "sources" not in path and "»" not in s and "says" not in path:
            warn.append("%s: %s" % (path, s[:140]))
        return s
    return x


def topic(t):
    return t if t in TOPICS else "andet"


def main():
    global TOPICS
    st = load("data", "static.json")
    TOPICS = {t["id"] for t in st["topics"]}
    parties, pdeb = [], []
    for pid in IDS:
        p = clean(load("data", "party-%s.json" % pid), pid)
        fix_urls(p)
        p["id"] = pid
        p.update(st["partyMeta"][pid])
        p["officialName"] = p.get("name", "")
        p["name"], p["nick"], p["short"] = NAMES[pid]
        for d in p.pop("currentDebates", []):
            d["party"] = pid
            d["topic"] = topic(d.get("topic"))
            if d.get("summary") and d.get("date"):
                pdeb.append(d)
        for k, v in list(p.get("positions", {}).items()):
            if k not in TOPICS or not isinstance(v, dict) or "text" not in v:
                p["positions"].pop(k)
            else:
                v["score"] = int(SCORES[k][SORDER.index(pid)]) if k in SCORES else max(1, min(5, int(round(v.get("score", 3)))))
        if pid == "df":
            p.pop("vsDF", None)
        p.setdefault("leader", {})
        parties.append(p)
    extra = clean(load("data", "df-extra.json"), "dfx")
    for b in extra.get("argumentBank", []):
        b["topic"] = topic(b.get("topic"))
    career = clean(load("data", "career.json"), "career")
    nat = clean(load("data", "national.json"), "nat")
    fix_urls(extra)
    fix_urls(nat)

    ts = {"built": datetime.now().strftime("%Y-%m-%d"), "topics": st["topics"], "pseudo": st["pseudo"], "election": st["election"],
          "government": st["government"], "parties": parties, "dfExtra": extra, "career": career, "hooks": st["hooks"], "moves": st["moves"],
          "checklist": st["checklist"], "format": st["format"], "plan": st["plan"]}
    os.makedirs(D("site"), exist_ok=True)
    js = "window.TS = " + json.dumps(ts, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + ";\n"
    open(D("site", "data.js"), "w", encoding="utf-8").write(js)

    # ---- live-dokumenter (sidens database) ----
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    os.makedirs(D("live"), exist_ok=True)
    items = []
    for d in nat.get("nationalDebates", []):
        d["topic"] = topic(d.get("topic"))
        d["partyPositions"] = {k: v for k, v in d.get("partyPositions", {}).items() if k in IDS and v and not BANNED.search(v)}
        d["heat"] = max(1, min(5, int(d.get("heat", 3))))
        items.append(d)
    cal = [c for c in nat.get("calendar", []) if re.match(r"^\d{4}-\d{2}-\d{2}$", c.get("date", ""))]
    polls = nat.get("polls", {})
    polls["latest"] = [p for p in polls.get("latest", []) if len(p.get("numbers", {})) >= 10]
    if polls.get("note"):
        polls["note"] = " ".join(re.split(r"(?<=[.!?])\s+(?=[A-ZÆØÅ])", polls["note"])[:2])
    HOST = {"tv2.dk": "TV 2", "dr.dk": "DR", "altinget.dk": "Altinget", "ft.dk": "Folketinget", "politiken.dk": "Politiken", "berlingske.dk": "Berlingske",
            "jyllands-posten.dk": "Jyllands-Posten", "ing.dk": "Ingeniøren", "voxmeter.dk": "Voxmeter", "ritzau.dk": "Ritzau", "sn.dk": "Sjællandske Nyheder",
            "jv.dk": "JydskeVestkysten", "arbejderen.dk": "Arbejderen", "lex.dk": "Lex", "wikipedia.org": "Wikipedia", "aeldresagen.dk": "Ældre Sagen",
            "information.dk": "Information", "avisendanmark.dk": "Avisen Danmark", "borsen.dk": "Børsen", "tv2ostjylland.dk": "TV 2 Østjylland", "fm.dk": "Finansministeriet"}

    def host(u):
        h = re.sub(r"^https?://(www\.)?", "", u or "").split("/")[0]
        for k, v in HOST.items():
            if h == k or h.endswith("." + k):
                return v
        return h or "Nyhed"

    def lead(t):
        first = re.split(r"(?<=[.!?])\s+(?=[A-ZÆØÅ»])", t)[0]
        return first if len(first) <= 240 else first[:237].rsplit(" ", 1)[0] + " …"

    news, seen = [], {}
    for d in sorted(pdeb, key=lambda x: x["date"], reverse=True):
        src = (d.get("sources") or [{}])[0]
        key = src.get("url") or re.sub(r"\W+", "", d["title"].lower())[:28]
        if key in seen:
            if d["party"] not in seen[key]["parties"]:
                seen[key]["parties"].append(d["party"])
            continue
        item = {"id": "pd-%s-%s" % (d["party"], d["date"]), "date": d["date"], "parties": [d["party"]], "title": d["title"], "text": lead(d["summary"]),
                "url": src.get("url", ""), "source": host(src.get("url", ""))}
        seen[key] = item
        news.append(item)
    docs = {"meta": {"updatedAt": now, "polls": polls, "calendar": cal},
            "national": {"updatedAt": now, "items": items},
            "partydebates": {"updatedAt": now, "items": pdeb},
            "news": {"updatedAt": now, "items": news[:60]}}
    for k, v in docs.items():
        json.dump(v, open(D("live", k + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("data.js %d KB | partier %d | partidebatter %d | nationale %d | nyheder %d | kalender %d | målinger %d" % (
        len(js.encode()) // 1024, len(parties), len(pdeb), len(items), len(news), len(cal), len(polls.get("latest", []))))
    for p in parties:
        miss = [t for t in TOPICS if t not in p.get("positions", {})]
        short = [k for k, n in (("keyIssues", 5), ("history", 6), ("people", 5), ("typicalArguments", 4), ("vocabulary", 3)) if len(p.get(k, [])) < n]
        nd = sum(1 for d in pdeb if d["party"] == p["id"])
        if miss or short or nd < 3:
            print("  ! %s mangler: emner %s | korte lister %s | debatter %d" % (p["id"], miss, short, nd))
    print("ARBEJDSNOTER: %d" % len(warn))
    for w in warn[:int(sys.argv[1]) if len(sys.argv) > 1 else 12]:
        print("   ", w)


if __name__ == "__main__":
    main()
