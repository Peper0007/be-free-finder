"""Donnerie.be — Belgian giveaway site (WordPress). Everything there is free.

New ads come from the RSS feed (/feed/); photo and place are read from the ad page
(og:image and the listing's details), only for ads we haven't processed yet.
"""
from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from ..common import Ad, clean, get, log

BASE = "https://donnerie.be"
FEED = BASE + "/feed/"
_NS = {"content": "http://purl.org/rss/1.0/modules/content/"}
_TAGS = re.compile(r"<[^>]+>")
_OG_IMAGE = re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', re.I)
_IMG = re.compile(r'<img[^>]+src=["\'](https://donnerie\.be/wp-content/uploads/[^"\']+)', re.I)
_CITY = re.compile(r'id="cp_city"[^>]*>\s*<span>[^<]*</span>\s*([^<]{1,60})', re.I)
_ZIP = re.compile(r'id="cp_zipcode"[^>]*>\s*<span>[^<]*</span>\s*([^<]{1,10})', re.I)


def _text(s: str | None) -> str:
    return clean(html.unescape(_TAGS.sub(" ", s or "")))


def parse_feed(xml: str) -> list[Ad]:
    root = ET.fromstring(xml)
    ads: list[Ad] = []
    for item in root.iter("item"):
        link = (item.findtext("link") or "").strip()
        if "/annonces/" not in link:
            continue
        slug = link.rstrip("/").rsplit("/", 1)[-1]
        body = item.findtext("content:encoded", namespaces=_NS) or item.findtext("description") or ""
        body = re.sub(r"The post .* first appeared on .*", "", body, flags=re.S)
        ts = 0.0
        try:
            ts = parsedate_to_datetime(item.findtext("pubDate") or "").timestamp()
        except (TypeError, ValueError):
            pass
        ads.append(Ad(source="donnerie", ad_id=slug, title=_text(item.findtext("title")), url=link,
                      description=_text(body)[:1500], posted_at=ts,
                      posted=(item.findtext("pubDate") or "")[5:16], needs_details=True))
    return ads


def enrich(ad: Ad) -> None:
    """Photo and place from the ad page."""
    try:
        page = get(ad.url, pause=0.5, retries=1).text
    except Exception as exc:
        log.warning("donnerie details failed for %s: %s", ad.url, exc)
        return
    photos = _OG_IMAGE.findall(page) + _IMG.findall(page)
    seen: list[str] = []
    for p in photos:
        if p not in seen and "logo" not in p.lower() and "cropped-" not in p:
            seen.append(p)
    ad.photos = seen[:4]
    city, zipc = _CITY.search(page), _ZIP.search(page)
    place = " ".join(clean(html.unescape(m.group(1))) for m in (zipc, city) if m)
    if place:
        ad.location = place
    ad.needs_details = False


def fetch(seen=None) -> list[Ad]:
    xml = get(FEED, pause=0.5).text
    ads = parse_feed(xml)
    log.info("donnerie feed: %s ads", len(ads))
    return ads
