"""Pickup area: is the ad near home (Brussels), or will the seller ship it?"""
from __future__ import annotations

import re
import unicodedata

from .common import Ad

# NL: verzenden, opsturen, bpost…  FR: envoi, livraison, expédition…
_SHIPS = re.compile(r"verzend|verzonden|opsturen|op te sturen|\bbpost\b|postnl|mondial relay|\bpakket|"
                    r"envoi|envoy|exp[ée]di|livraison|livrable|colis|vinted go", re.I)
_ONLY_PICKUP = re.compile(r"enkel afhalen|alleen afhalen|alleen ophalen|enkel ophalen|af te halen|op te halen|"
                          r"niet verzonden|geen verzending|à venir chercher|a venir chercher|à enlever|a enlever|"
                          r"pas d'envoi|pas d.exp[ée]dition|sur place uniquement", re.I)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s)


def _postcode(location: str) -> int | None:
    m = re.search(r"\b([1-9]\d{3})\b", location or "")
    return int(m.group(1)) if m else None


def is_near(location: str, home: dict) -> bool:
    loc = " " + _norm(location) + " "
    pc = _postcode(location)
    rng = home.get("postcodes") or []
    if pc and len(rng) == 2 and int(rng[0]) <= pc <= int(rng[1]):
        return True
    places = [home.get("city") or ""] + list(home.get("nearby") or [])
    return any(p and (" " + _norm(p).strip() + " ") in loc for p in places)


def ships(ad: Ad) -> bool:
    text = f"{ad.title} {ad.description}"
    if _ONLY_PICKUP.search(text):
        return False
    # 2dehands: the «delivery» field says «Verzenden» / «Ophalen of Verzenden» when the seller ships
    if "verzend" in (ad.delivery or "").lower() or "envoi" in (ad.delivery or "").lower():
        return True
    return bool(_SHIPS.search(text))


def home_hint(home: dict) -> str:
    city = home.get("city") or ""
    if not city:
        return ""
    return (f"Вещи забирает помощник владельца в городе {city} и рядом "
            f"({', '.join((home.get('nearby') or [])[:25])} и т. п.). По Бельгии он ездит, но далеко — только ради "
            "действительно ценного. Если вещь далеко от Брюсселя и продавец не отправляет её (bpost и т. п.), "
            "снижай оценку на 1–2 балла: ехать за ней обычно не окупается.")
