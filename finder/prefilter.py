"""Cheap keyword pre-filter: drops obvious junk before spending AI quota.

Edit SKIP_WORDS freely. Matching is case-insensitive on the title only
(descriptions often mention unrelated words).
"""
from __future__ import annotations

import re

from .common import Ad

# Two dictionaries: Dutch (NL) and French (FR). Animals, food, building materials, bulky furniture,
# baby gear, broken things, services, «make an offer» ads.
SKIP_WORDS = [
    # NL — dieren
    r"\bkat(je|ten|tje)?s?\b", r"\bpoes", r"\bkitten", r"\bhond(je|en)?\b", r"\bpup(s|py|je)?\b", r"konijn",
    r"cavia", r"hamster", r"papegaai", r"parkiet", r"\bvissen\b", r"kippen?\b", r"\bkuikens?\b", r"\bgeit",
    r"\bschaap", r"herplaatsing", r"zoekt (een )?(nieuw|warm)", r"\bthuis gezocht", r"\bgevonden\b", r"vermist",
    # FR — animaux
    r"\bchat(on|te|ons|s)?\b", r"\bchiens?\b", r"chiot", r"lapin", r"cobaye", r"perroquet", r"poule", r"poussin",
    r"\bch[eè]vre", r"mouton", r"cherche (un )?foyer", r"\badoption\b", r"\btrouv[ée]e?\b", r"\bperdu",
    # NL — eten, planten, aarde, hout
    r"\baarde\b", r"potgrond", r"\bmest\b", r"brandhout", r"openhaardhout", r"\bplant(en|je)?\b", r"stekje",
    r"\bfruit\b", r"groenten", r"\bvoeding\b", r"hooi", r"\bstro\b",
    # FR — nourriture, plantes, terre, bois
    r"\bterre\b", r"terreau", r"fumier", r"bois de chauffage", r"bois à brûler", r"\bplantes?\b", r"bouture",
    r"légumes", r"nourriture", r"\bfoin\b", r"\bpaille\b",
    # NL — bouw / groot
    r"dakpan", r"bakste(en|nen)", r"\btegels?\b", r"\bramen\b", r"\braam\b", r"\bdeur(en)?\b", r"boiler",
    r"radiator", r"matras", r"\bbank(stel)?\b", r"zetel", r"\bsofa\b", r"\bbed(den)?\b", r"slaapkamer",
    r"kleerkast", r"\bkast(en)?\b", r"keuken", r"eettafel", r"\bstoel(en)?\b", r"fauteuil", r"koelkast",
    r"\bfrigo\b", r"wasmachine", r"droogkast", r"vaatwas", r"diepvries", r"\boven\b", r"fornuis", r"\bbanden\b",
    r"\bvelgen\b", r"pallet", r"\bhout\b", r"planken", r"isolatie", r"\bpuin\b", r"\bgrond\b", r"\bzand\b",
    r"klinkers", r"gyproc", r"\bglas\b", r"\bplexi",
    # FR — bricolage / encombrant
    r"tuiles?\b", r"briques?", r"carrelage", r"fen[eê]tres?", r"\bportes?\b", r"radiateur", r"matelas",
    r"canap[ée]", r"divan", r"\blits?\b", r"armoire", r"garde-robe", r"\bcuisine\b", r"\btables?\b", r"\bchaises?\b",
    r"frigo", r"r[ée]frig[ée]rateur", r"lave-linge", r"machine à laver", r"s[eè]che-linge", r"lave-vaisselle",
    r"cong[ée]lateur", r"\bfour\b", r"cuisini[eè]re", r"\bpneus?\b", r"\bjantes?\b", r"palettes?", r"planches?",
    r"\bsable\b", r"gravier", r"\bvitre",
    # NL — baby / kinderen, schoolboeken, medicijnen
    r"\bbaby", r"kinderkleding", r"kinderwagen", r"buggy", r"maxi-?cosi", r"\bbox\b", r"luiers", r"schoolboek",
    r"medicijn",
    # FR — bébé / enfants, manuels scolaires, médicaments
    r"\bb[ée]b[ée]", r"poussette", r"\bparc\b", r"\blanges?\b", r"v[eê]tements? (enfant|fille|gar[cç]on)",
    r"manuels? scolaire", r"m[ée]dicament",
    # NL / FR — kapot / cassé
    r"\bdefect\b", r"\bkapot\b", r"werkt niet", r"\bhs\b", r"en panne", r"\bcass[ée]e?\b", r"ne fonctionne pas",
    # NL / FR — bieden / faire offre (не бесплатно: «предложите цену»)
    r"\bbieden\b", r"\bbod\b", r"faire offre", r"\boffre\b",
    # NL / FR — diensten, werk, woning, gezocht
    r"\bdienst", r"\bwerk\b", r"vacature", r"\bklus", r"ontruiming", r"leeghalen", r"\bkamer te huur",
    r"gezocht", r"\bgevraagd\b", r"\bservice", r"d[ée]barras", r"\bemploi\b", r"[àa] louer", r"\bcherche\b",
    r"\brecherche\b",
]
_SKIP_RE = re.compile("|".join(SKIP_WORDS), re.I)

# Words that hint at collectible / vintage value: such titles always go to the AI,
# even if they also contain a "junk" word ("Зайчета от порцелан", "Ретро шкаф").
KEEP_WORDS = [
    # NL
    r"porselein", r"\bbeeld(je)?", r"keramiek", r"\bbrons", r"kristal", r"\bkoper", r"\bvintage\b", r"\bretro\b",
    r"\bantiek", r"\boud(e)?\b", r"verzamel", r"\bbrocante", r"design", r"jaren ?[2-8]0", r"\bemaille",
    r"\bzilver", r"\bgoud", r"\bvinyl\b", r"\blp'?s?\b", r"\bplaten\b", r"curiosa", r"art deco", r"art nouveau",
    # FR
    r"porcelaine", r"statuette", r"figurine", r"c[ée]ramique", r"\bbronze", r"cristal", r"\bcuivre", r"\blaiton",
    r"\bancien", r"\bvieux\b", r"\bvieille", r"collection", r"\bbrocante", r"ann[ée]es ?[2-8]0", r"[ée]maill[ée]",
    r"\bargent\b", r"\bor\b", r"\bdisques?\b", r"\b33 ?tours", r"\b45 ?tours", r"curiosit",
]
_KEEP_RE = re.compile("|".join(KEEP_WORDS), re.I)

# Parts of the ad URL that mark whole sub-categories to skip (2dehands URL paths).
SKIP_URL_PARTS = ["/kinderen-en-baby-s/kinderwagens", "/kinderen-en-baby-s/babykleding", "/kinderen-en-baby-s/kinderkleding",
                  "/huis-en-inrichting/banken", "/huis-en-inrichting/bedden", "/huis-en-inrichting/kasten",
                  "/huis-en-inrichting/keuken", "/huis-en-inrichting/stoelen", "/huis-en-inrichting/tafels",
                  "/doe-het-zelf-en-bouw/bouwmaterialen", "/doe-het-zelf-en-bouw/hout", "/doe-het-zelf-en-bouw/sanitair",
                  "/tuin-en-terras/planten", "/tuin-en-terras/aarde", "/witgoed-en-apparatuur/koelkasten",
                  "/fietsen-en-brommers/fietsen-"]
_SKIP_URL = list(SKIP_URL_PARTS)


def _compile(words: list[str]) -> re.Pattern | None:
    good = []
    for w in words or []:
        w = (w or "").strip()
        if not w:
            continue
        try:
            re.compile(w)
            good.append(w)
        except re.error:
            good.append(re.escape(w))  # treat broken regex as plain text
    return re.compile("|".join(good), re.I) if good else None


# «Охота»: the owner's own words (brands, models, makers). Such ads are never dropped as junk,
# go to the AI first and always reach Telegram with sound, whatever the score. Empty by default.
_HUNT: list[tuple[str, re.Pattern]] = []


def configure(skip_words: list[str] | None = None, keep_words: list[str] | None = None,
              skip_url_parts: list[str] | None = None, hunt_words: list[str] | None = None) -> None:
    """Replace the built-in lists (used when the dashboard provides its own)."""
    global _SKIP_RE, _KEEP_RE, _SKIP_URL, _HUNT
    if hunt_words is not None:
        _HUNT = []
        for w in hunt_words:
            w = (w or "").strip()
            if w:
                rx = _compile([w])
                if rx is not None:
                    _HUNT.append((w, rx))
    if skip_url_parts is not None:
        _SKIP_URL = [p.strip() for p in skip_url_parts if p and p.strip()]
    if skip_words is not None:
        _SKIP_RE = _compile(skip_words)
    if keep_words is not None:
        _KEEP_RE = _compile(keep_words)


def hunt_match(ad: Ad) -> str:
    """The first «охота» word found in the title or description ('' = none)."""
    text = f"{ad.title or ''} {ad.description or ''}"
    for word, rx in _HUNT:
        if rx.search(text):
            return word
    return ""


def is_junk(ad: Ad) -> bool:
    if hunt_match(ad):
        return False
    url = ad.url or ""
    if any(part in url for part in _SKIP_URL):
        return True
    title = ad.title or ""
    if _SKIP_RE is None or not _SKIP_RE.search(title):
        return False
    return not (_KEEP_RE is not None and _KEEP_RE.search(title))
