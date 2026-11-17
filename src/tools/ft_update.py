#!/usr/bin/env python3
"""Henter det nyeste fra Folketingets åbne data (oda.ft.dk) og skriver ét JSON-dokument,
som Talerstolen viser under "Live fra Folketinget".

Brug:  python3 ft_update.py ud.json
Kun standardbiblioteket. Ingen nøgle nødvendig (åbent API).
"""
import json, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone

API = "https://oda.ft.dk/api/"
PARTY = {"S": "s", "SF": "sf", "V": "v", "DF": "df", "LA": "la", "M": "m", "KF": "k", "EL": "el",
         "DD": "dd", "RV": "rv", "ALT": "alt", "BP": "bp", "IA": "na", "N": "na", "JF": "na", "SP": "na",
         "UFG": "ufg"}
SLUG = {"L": "lovforslag", "B": "beslutningsforslag", "F": "forespoergsel", "S": "spoergsmaal",
        "V": "vedtagelse", "R": "redegoerelse"}


def get(path, params=None, pages=1):
    """GET mod ODA med paging. Returnerer listen i 'value'."""
    q = {"$format": "json"}
    q.update(params or {})
    url = API + urllib.parse.quote(path) + "?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)
    out = []
    for _ in range(pages):
        for attempt in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "ft-feed/1.0"}), timeout=40) as r:
                    d = json.load(r)
                break
            except Exception as e:  # netværksfejl: prøv igen
                if attempt == 2:
                    raise
                time.sleep(2 + attempt * 3)
        if "value" not in d:
            return d
        out += d["value"]
        url = d.get("odata.nextLink")
        if not url:
            break
    return out


def split_top(s):
    """Del 'S, SF, Navn (EL) og Navn (UFG)' i led på øverste parentesniveau."""
    items, depth, cur = [], 0, ""
    s = re.sub(r"\s+og\s+", ", ", s)
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            items.append(cur.strip()); cur = ""
        else:
            cur += ch
    if cur.strip():
        items.append(cur.strip())
    return items


def parse_side(seg):
    """'93 (S, SF, ... )' -> (93, ['s','sf'], ['Navn (EL)'])"""
    m = re.match(r"\s*(\d+)\s*(?:\((.*)\))?", seg.strip(), re.S)
    if not m:
        return 0, [], []
    n, inner = int(m.group(1)), (m.group(2) or "")
    parties, singles = [], []
    for it in split_top(inner):
        if it in PARTY:
            pid = PARTY[it]
            if pid not in parties:
                parties.append(pid)
        elif it:
            singles.append(it)
    return n, parties, singles


def parse_konklusion(k):
    k = (k or "").replace("\n", " ")
    m = re.search(r"For stemte(.*?),\s*imod stemte(.*?),\s*hverken for eller imod stemte(.*?)\.?\s*$", k, re.S | re.I)
    if not m:
        return None
    f, a, n = (parse_side(x) for x in m.groups())
    return {"forN": f[0], "for": f[1], "forSolo": f[2], "againstN": a[0], "against": a[1], "againstSolo": a[2],
            "abstainN": n[0], "abstain": n[1], "abstainSolo": n[2]}


def sag_url(kode, sag):
    slug = SLUG.get((sag.get("nummerprefix") or "").strip())
    if not slug or not sag.get("nummernumerisk"):
        return "https://www.ft.dk/"
    return "https://www.ft.dk/samling/%s/%s/%s%s/index.htm" % (kode, slug, sag["nummerprefix"].strip(), sag["nummernumerisk"].strip())


def main(out_path):
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%dT%H:%M:%S")
    per = get("Periode", {"$filter": "type eq 'samling' and startdato le datetime'%s'" % today, "$orderby": "startdato desc", "$top": "1"})[0]
    pid, kode = per["id"], per["kode"]

    # 1) Grupper og medlemmer -> person-id til parti + aktuelle mandater
    groups = get("Aktør", {"$filter": "typeid eq 4 and periodeid eq %d" % pid, "$select": "id,navn,gruppenavnkort"}, pages=3)
    person_party, seats, names_by = {}, {}, {}
    for g in groups:
        short = (g.get("gruppenavnkort") or "").strip()
        party = PARTY.get(short)
        if not party:
            continue
        rel = get("AktørAktør", {"$filter": "tilaktørid eq %d and rolleid eq 15" % g["id"], "$expand": "FraAktør",
                                 "$select": "fraaktørid,startdato,slutdato,FraAktør/navn"}, pages=5)
        members = {}
        for r in rel:
            if (r.get("startdato") or "") <= today and (not r.get("slutdato") or r["slutdato"] > today):
                members[r["fraaktørid"]] = ((r.get("FraAktør") or {}).get("navn") or "").strip()
        for m in members:
            person_party[m] = party
        seats[party] = seats.get(party, 0) + len(members)
        label = "" if party not in ("na", "ufg") else (" (%s)" % short if party == "na" else "")
        names_by.setdefault(party, []).extend(n + label for n in members.values() if n)
    for k in names_by:
        names_by[k].sort()

    def actors(sag, roles):
        ps, names = [], []
        for sa in sag.get("SagAktør", []):
            if sa.get("rolleid") in roles:
                a = sa.get("Aktør") or {}
                if a.get("typeid") == 5:
                    names.append(a.get("navn"))
                    p = person_party.get(a.get("id"))
                    if p and p not in ps:
                        ps.append(p)
        return ps, names

    sel = "id,typeid,titel,titelkort,nummer,nummerprefix,nummernumerisk,resume,opdateringsdato,statusid,SagAktør/rolleid,SagAktør/Aktør/id,SagAktør/Aktør/navn,SagAktør/Aktør/typeid"
    status = {s["id"]: s["status"] for s in get("Sagsstatus", {"$top": "100"}, pages=2)}

    # 2) Forslag: lovforslag (3), beslutningsforslag (5), forespørgsler (2)
    proposals = []
    for s in get("Sag", {"$filter": "periodeid eq %d and (typeid eq 3 or typeid eq 5 or typeid eq 2)" % pid, "$orderby": "opdateringsdato desc",
                         "$top": "70", "$expand": "SagAktør/Aktør", "$select": sel}):
        ps, names = actors(s, (16, 15, 2))
        gov = any(sa.get("rolleid") == 19 for sa in s.get("SagAktør", []))
        citizen = "borgerforslag" in (s.get("titel") or "").lower()
        if citizen:
            ps, names = [], ["Borgerforslag med 50.000 underskrifter"]
        proposals.append({
            "id": s["id"], "kind": "Borgerforslag" if citizen else {3: "Lovforslag", 5: "Beslutningsforslag", 2: "Forespørgsel"}[s["typeid"]],
            "nr": (s.get("nummer") or "").strip(), "title": (s.get("titelkort") or s.get("titel") or "").strip(),
            "long": (s.get("titel") or "").strip()[:400], "resume": re.sub(r"\s+", " ", (s.get("resume") or ""))[:700],
            "date": (s.get("opdateringsdato") or "")[:10], "status": status.get(s.get("statusid"), ""),
            "parties": ps, "by": (names[0] + (" m.fl." if len(names) > 1 else "")) if names else ("Regeringen" if gov or s["typeid"] == 3 else ""),
            "gov": bool(gov or (s["typeid"] == 3 and not names)), "url": sag_url(kode, s)})

    # 3) § 20-spørgsmål til ministrene
    questions = []
    for s in get("Sag", {"$filter": "periodeid eq %d and typeid eq 10" % pid, "$orderby": "id desc", "$top": "60",
                         "$expand": "SagAktør/Aktør", "$select": sel}):
        ps, names = actors(s, (10, 5))
        minister = next((sa["Aktør"]["navn"] for sa in s.get("SagAktør", []) if sa.get("rolleid") == 14 and sa.get("Aktør")), "")
        questions.append({"id": s["id"], "nr": (s.get("nummer") or "").strip(), "title": (s.get("titelkort") or "").strip(),
                          "long": re.sub(r"\s+", " ", (s.get("titel") or ""))[:420], "date": (s.get("opdateringsdato") or "")[:10],
                          "parties": ps, "by": names[0] if names else "", "to": minister, "url": sag_url(kode, s)})

    # 4) Afstemninger: hvem stemte for og imod (kan høre til en tidligere samling -> slå samlingskoden op)
    kodes = {p["id"]: p["kode"] for p in get("Periode", {"$orderby": "id desc", "$top": "12", "$select": "id,kode"})}
    votes = []
    for a in get("Afstemning", {"$orderby": "id desc", "$top": "60", "$expand": "Sagstrin/Sag"}):
        st = a.get("Sagstrin") or {}
        sag = st.get("Sag") or {}
        pk = parse_konklusion(a.get("konklusion"))
        if not pk or not sag:
            continue
        v = {"id": a["id"], "date": (st.get("dato") or a.get("opdateringsdato") or "")[:10], "passed": bool(a.get("vedtaget")),
             "final": a.get("typeid") == 1, "amendment": a.get("typeid") == 4, "step": (st.get("titel") or "").strip(),
             "nr": (sag.get("nummer") or "").strip(), "title": (sag.get("titelkort") or sag.get("titel") or "").strip(), "url": sag_url(kodes.get(sag.get("periodeid"), kode), sag)}
        v.update(pk)
        votes.append(v)
    votes = [v for v in votes if not v["amendment"]][:30]

    doc = {"updatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "samling": per["titel"], "source": "Folketingets åbne data (oda.ft.dk)",
           "seats": seats, "seatsTotal": sum(seats.values()), "members": names_by,
           "proposals": proposals[:60], "questions": questions[:50], "votes": votes}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    print("OK %s | mandater %s (i alt %d) | forslag %d | spørgsmål %d | afstemninger %d | %d KB" % (
        per["titel"], json.dumps(seats), doc["seatsTotal"], len(proposals), len(questions), len(votes), len(json.dumps(doc, ensure_ascii=False).encode()) // 1024))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ft.json")
