"""2dehands.be / 2ememain.be (one platform, NL and FR interface, same ads) and Marktplaats.nl.

The site's own search endpoint (/lrp/api/search, not disallowed in robots.txt) returns JSON.
Free ads = price range 0 («Gratis» / «Gratuit»); it also returns «Bieden» ads with a 0 € minimum bid,
which are skipped unless include_bids is on. Cheap ads: price range ≤ N € in chosen categories.
Results are sorted newest first, so paging stops once a page holds nothing new.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from ..common import Ad, clean, get, log, stop_when_seen

SITES = {
    "2dehands": "https://www.2dehands.be",
    "marktplaats": "https://www.marktplaats.nl",
}
SEARCH = ("{base}/lrp/api/search?l1CategoryId={cat}&limit={limit}&offset={offset}"
          "&sortBy=SORT_INDEX&sortOrder=DECREASING&viewOptions=list-view"
          "&attributeRanges[]=PriceCents:null:{max_cents}")
PAGE = 100

# 2dehands top-level categories worth checking for free stuff (id: slug). Excluded on purpose:
# cars (91), motorbikes (678), services (1098), real estate (1032), animals (395), contacts (378),
# holidays (856), tickets (1984), boats (976), caravans (289).
CATEGORIES = {
    1: "antiek-en-kunst", 31: "audio-tv-en-foto", 201: "boeken", 1744: "cd-s-en-dvd-s",
    322: "computers-en-software", 356: "games-en-spelcomputers", 1826: "handtassen-en-accessoires",
    1099: "hobby-en-vrije-tijd", 504: "huis-en-inrichting", 537: "elektronische-apparatuur",
    621: "kleding-dames", 1776: "kleding-heren", 728: "muziek-en-instrumenten",
    1784: "postzegels-en-munten", 784: "sport-en-fitness", 820: "telecommunicatie",
    895: "verzamelen", 428: "diversen", 1085: "zakelijke-goederen", 239: "doe-het-zelf-en-bouw",
    565: "kinderen-en-baby-s", 1847: "tuin-en-terras", 445: "fietsen-en-brommers", 2600: "auto-onderdelen",
    48: "auto-diversen",
}
# Checked by default. Left out after the first run (only 0/10 there, they ate the AI quota):
# bikes 445, car parts 2600 / 48, DIY & building 239, sport 784, garden 1847 — add them in the dashboard if needed.
# Kids 565 stays for Vinted (LEGO, Playmobil, branded kids' lots); baby gear is dropped by the word filter.
DEFAULT_FREE_CATS = [c for c in CATEGORIES if c not in (445, 2600, 48, 239, 784, 1847)]
DEFAULT_CHEAP_CATS = [1, 895, 1784, 1744, 728, 201]

_MONTHS = {"jan": 1, "feb": 2, "mrt": 3, "apr": 4, "mei": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9,
           "okt": 10, "nov": 11, "dec": 12, "janv": 1, "févr": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6,
           "juil": 7, "août": 8, "sept": 9, "oct": 10, "déc": 12}


def posted_ts(date: str, now: datetime | None = None) -> float:
    """«Vandaag» / «Gisteren» / «Eergisteren» / «22 nov 26» (FR: «Aujourd'hui», «Hier») → unix time (day precision).
    Today's ads get «now − 1 h» so they sort above yesterday's."""
    now = now or datetime.now()
    d = (date or "").strip().lower()
    if d in ("vandaag", "aujourd'hui", "aujourd’hui"):
        return (now - timedelta(hours=1)).timestamp()
    if d in ("gisteren", "hier"):
        return (now - timedelta(days=1)).replace(hour=12, minute=0).timestamp()
    if d in ("eergisteren", "avant-hier"):
        return (now - timedelta(days=2)).replace(hour=12, minute=0).timestamp()
    m = re.match(r"(\d{1,2})\s+([a-zéû]+)\.?\s+'?(\d{2,4})", d)
    if m and m.group(2) in _MONTHS:
        year = int(m.group(3))
        year += 2000 if year < 100 else 0
        try:
            return datetime(year, _MONTHS[m.group(2)], int(m.group(1)), 12).timestamp()
        except ValueError:
            return 0.0
    return 0.0


def _photo(url: str) -> str:
    url = url or ""
    if url.startswith("//"):
        url = "https:" + url
    # «…$_82.jpg» is a thumbnail; «$_85» is the large version
    return re.sub(r"\$_\d+\.jpg", "$_85.jpg", url)


def parse(data: dict, source: str, base: str, max_eur: float = 0.0, include_bids: bool = False) -> list[Ad]:
    ads: list[Ad] = []
    for li in data.get("listings") or []:
        info = li.get("priceInfo") or {}
        ptype = info.get("priceType")
        cents = int(info.get("priceCents") or 0)
        if max_eur <= 0:
            if ptype != "FREE" and not (include_bids and ptype == "MIN_BID" and cents == 0):
                continue
            price = 0.0
        else:
            if ptype not in ("FIXED", "FAST_BID", "MIN_BID") or cents <= 0 or cents > max_eur * 100:
                continue
            price = cents / 100
        if li.get("priorityProduct") == "DAGTOPPER" and li.get("l1CategoryId") == 1098:
            continue  # paid service ads
        loc = li.get("location") or {}
        if loc.get("abroad"):
            continue
        delivery = ""
        for a in (li.get("attributes") or []) + (li.get("extendedAttributes") or []):
            if a.get("key") == "delivery":
                delivery = ", ".join(a.get("values") or [a.get("value") or ""])
                break
        photos = [_photo(p.get("extraExtraLargeUrl") or p.get("largeUrl") or "") for p in (li.get("pictures") or [])]
        if not photos:
            photos = [_photo(u) for u in (li.get("imageUrls") or [])]
        date = li.get("date") or ""
        ads.append(Ad(
            source=source,
            ad_id=str(li.get("itemId") or ""),
            title=clean(li.get("title")),
            url=base + (li.get("vipUrl") or ""),
            location=clean(loc.get("cityName") or ""),
            description=clean(li.get("categorySpecificDescription") or li.get("description"))[:1500],
            photos=[p for p in photos if p][:4],
            posted=date,
            posted_at=posted_ts(date),
            delivery=delivery,
            price=price,
        ))
    return [a for a in ads if a.ad_id]


def _pages(source: str, cat: int, pages: int, max_eur: float, include_bids: bool, label: str):
    base = SITES[source]
    for page in range(pages):
        url = SEARCH.format(base=base, cat=cat, limit=PAGE, offset=page * PAGE,
                            max_cents=int(round(max_eur * 100)))
        try:
            resp = get(url, pause=1.0, headers={"Accept": "application/json"})
            if resp.status_code == 204 or not resp.content:
                return
            data = resp.json()
        except Exception as exc:
            log.warning("%s page %s failed: %s", label, page + 1, exc)
            return
        ads = parse(data, source, base, max_eur, include_bids)
        log.info("%s page %s: %s ads", label, page + 1, len(ads))
        if not data.get("listings"):
            return
        yield ads
        if (page + 1) * PAGE >= int(data.get("totalResultCount") or 0):
            return


def fetch(source: str = "2dehands", categories: list | None = None, pages: int = 3, seen=None,
          include_bids: bool = False) -> list[Ad]:
    """Free ads in each category; stops paging a category once it reaches ads we've already processed."""
    out: list[Ad] = []
    for cat in categories or DEFAULT_FREE_CATS:
        try:
            cat = int(cat)
        except (TypeError, ValueError):
            continue
        label = f"{source} {CATEGORIES.get(cat, cat)} gratis"
        out += stop_when_seen(_pages(source, cat, pages, 0.0, include_bids, label), seen, label, quiet_pages=1)
    return out


def fetch_cheap(categories: list | None, max_eur: float, pages: int = 2, seen=None,
                source: str = "2dehands") -> list[Ad]:
    out: list[Ad] = []
    for cat in categories or DEFAULT_CHEAP_CATS:
        try:
            cat = int(cat)
        except (TypeError, ValueError):
            continue
        label = f"{source} {CATEGORIES.get(cat, cat)} ≤{max_eur:g}€"
        out += stop_when_seen(_pages(source, cat, pages, float(max_eur), False, label), seen, label, quiet_pages=1)
    return out

