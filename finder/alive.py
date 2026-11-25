"""«Is the ad still online?» — re-checks open finds so removed ads leave «Находки» by themselves.

2dehands answers 404/410 for a removed ad, or shows a «niet meer beschikbaar» / «plus disponible» notice;
Donnerie marks given-away ads «Déjà pris».
Anything unclear (network error, 403, captcha) counts as «don't know» and changes nothing.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

from .common import log, session

_GONE_TEXT = re.compile(r"niet meer beschikbaar|is verwijderd|n'est plus disponible|a été supprimée|"
                        r"advertentie is gesloten|annonce est clôturée", re.I)
_GONE_DONNERIE = re.compile(r'id="cp_sold"[^>]*>\s*<span>[^<]*</span>\s*(oui|yes)|class="[^"]*\bsold\b', re.I)


def is_alive(url: str) -> bool | None:
    if not url:
        return None
    try:
        resp = session().get(url, timeout=20, allow_redirects=True)
    except Exception as exc:
        log.debug("alive check failed %s: %s", url, exc)
        return None
    if resp.status_code in (404, 410):
        return False
    if resp.status_code != 200:
        return None
    if "donnerie.be" in url:
        return not _GONE_DONNERIE.search(resp.text)
    if _GONE_TEXT.search(resp.text):
        return False
    return True


def check(items: list[dict], workers: int = 4) -> list[tuple[dict, bool | None]]:
    """items: [{id, url, ...}] → [(item, alive)]; a few in parallel, politely."""
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(zip(items, pool.map(lambda it: is_alive(it["url"]), items)))
