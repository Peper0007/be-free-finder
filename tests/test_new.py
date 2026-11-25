"""Offline tests (Belgium): 2dehands/Donnerie parsers, NL/FR word filter, early stop, pickup area, batched Gemini, alive check, digest, full run."""
import json
import os
import sys
import time
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from finder import ai, alive, common, geo
from finder.common import Ad, stop_when_seen
from finder.prefilter import is_junk
from finder.sources import donnerie, tweedehands


def listing(i, ptype, cents=0, title="Oude vaas", city="Ukkel", date="Vandaag", cat=1, delivery="Ophalen"):
    return {"itemId": f"m{i}", "title": title, "description": "kort", "categorySpecificDescription": "lange tekst",
            "priceInfo": {"priceCents": cents, "priceType": ptype}, "location": {"cityName": city, "abroad": False},
            "date": date, "l1CategoryId": cat, "vipUrl": f"/v/antiek-en-kunst/x/m{i}-oude-vaas",
            "attributes": [{"key": "delivery", "value": delivery, "values": [delivery]}],
            "pictures": [{"extraExtraLargeUrl": "https://images.2dehands.com/api/v1/x/images/ab/abc?rule=ecg_mp_eps$_85.jpg"}],
            "imageUrls": ["//images.2dehands.com/api/v1/x/images/ab/abc?rule=ecg_mp_eps$_82.jpg"]}


def test_tweedehands_parse():
    data = {"listings": [listing(1, "FREE"), listing(2, "MIN_BID"), listing(3, "FIXED", 350), listing(4, "FIXED", 1200),
                         listing(5, "FREE", title="Dakwerken gratis offerte", cat=1098) | {"priorityProduct": "DAGTOPPER"}]}
    base = "https://www.2dehands.be"
    free = tweedehands.parse(data, "2dehands", base)
    assert [a.ad_id for a in free] == ["m1"], free
    a = free[0]
    assert a.url == base + "/v/antiek-en-kunst/x/m1-oude-vaas" and a.location == "Ukkel" and a.delivery == "Ophalen"
    assert a.photos[0].startswith("https://") and a.posted_at > 0 and a.description == "lange tekst"
    assert [a.ad_id for a in tweedehands.parse(data, "2dehands", base, include_bids=True)] == ["m1", "m2"]
    cheap = tweedehands.parse(data, "2dehands", base, max_eur=5)
    assert [(a.ad_id, a.price) for a in cheap] == [("m3", 3.5)]


def test_posted_ts():
    from datetime import datetime
    now = datetime(2026, 11, 25, 14, 0)
    t = tweedehands.posted_ts
    assert t("Vandaag", now) > t("Gisteren", now) > t("Eergisteren", now) > t("22 nov 26", now) > 0
    assert datetime.fromtimestamp(t("22 nov 26", now)).date().isoformat() == "2026-11-22"
    assert t("Hier", now) == t("Gisteren", now) and t("???", now) == 0


def test_donnerie_feed():
    xml = """<?xml version="1.0"?><rss xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel>
    <item><title>Encyclop&#233;die</title><link>https://donnerie.be/annonces/encyclopedie-2/</link>
    <pubDate>Tue, 20 Oct 2026 09:29:48 +0000</pubDate><description>x</description>
    <content:encoded><![CDATA[<p>Donne une encyclopédie Larousse.</p><p>The post <a href="#">E</a> first appeared on Donnerie.be.</p>]]></content:encoded></item>
    </channel></rss>"""
    ads = donnerie.parse_feed(xml)
    assert len(ads) == 1 and ads[0].ad_id == "encyclopedie-2" and ads[0].title == "Encyclopédie"
    assert ads[0].description == "Donne une encyclopédie Larousse." and ads[0].posted_at > 0 and ads[0].needs_details
    page = ('<meta property="og:image" content="https://donnerie.be/wp-content/uploads/2026/10/1-375x500.jpeg">'
            '<li id="cp_city" class=""><span>Ville:</span> Uccle</li><li id="cp_zipcode" class=""><span>Code postal:</span> 1180</li>')
    with mock.patch.object(donnerie, "get", lambda url, **kw: mock.Mock(text=page)):
        donnerie.enrich(ads[0])
    assert ads[0].location == "1180 Uccle" and ads[0].photos == ["https://donnerie.be/wp-content/uploads/2026/10/1-375x500.jpeg"]


def test_prefilter_nl_fr():
    junk = ["Gratis kittens", "Canapé 3 places", "Zetel gratis af te halen", "Chiots à donner", "Brandhout",
            "Kinderwagen", "Appareil photo HS", "Wasmachine defect", "Matelas 140x200", "Bieden"]
    good = ["Oude porseleinen beeldjes", "Partij LP platen", "Masques africains", "Ancienne horloge",
            "Vintage kast jaren 60", "Lot de BD Tintin", "Val Saint Lambert vaas", "Fax Brother"]
    for t in junk:
        assert is_junk(Ad("x", "1", t, "u")), t
    for t in good:
        assert not is_junk(Ad("x", "1", t, "u")), t


def test_stop_when_seen():
    pages = [[Ad("2dehands", str(i * 10 + j), "t", "u") for j in range(3)] for i in range(6)]
    fetched = []

    def gen():
        for p in pages:
            fetched.append(1)
            yield p
    seen = {a.key: 1 for p in pages[1:] for a in p}  # only page 1 has new ads
    out = stop_when_seen(gen(), seen, "t")
    assert len(fetched) == 3 and len(out) == 9, (len(fetched), len(out))  # page1 new, 2-3 quiet → stop
    assert len(stop_when_seen(iter(pages), None, "t")) == 18


def test_geo():
    from finder.remote import DEFAULTS
    home = DEFAULTS["home"]
    assert geo.is_near("Ukkel", home) and geo.is_near("1180 Uccle", home) and geo.is_near("Sint-Pieters-Leeuw 1600", home)
    assert geo.is_near("Schaerbeek", home) and geo.is_near("Braine-l'Alleud", home)
    assert not geo.is_near("Gent", home) and not geo.is_near("9000 Gent", home) and not geo.is_near("Luik", home)
    assert geo.ships(Ad("2dehands", "1", "Vaas", "u", delivery="Ophalen, Verzenden"))
    assert geo.ships(Ad("2dehands", "1", "Vase", "u", description="Envoi possible par bpost"))
    assert not geo.ships(Ad("2dehands", "1", "Vaas", "u", delivery="Ophalen", description="Gratis af te halen"))
    assert "Brussel" in geo.home_hint(home)


class FakeResp:
    def __init__(self, status, payload=None, text=""):
        self.status_code, self._payload, self.text = status, payload, text or json.dumps(payload or {})

    def json(self):
        return self._payload


def gemini_answer(items):
    return FakeResp(200, {"candidates": [{"content": {"parts": [{"text": json.dumps(items, ensure_ascii=False)}]}}]})


def test_ai_batch():
    os.environ["GEMINI_API_KEY"] = "x"
    ads = [Ad("2dehands", str(i), f"Ding {i}", "u", price=2 if i == 2 else 0) for i in range(1, 4)]
    sent = {}

    def post(url, params, json, timeout):
        sent["body"] = json
        return gemini_answer([{"n": 3, "score": 9, "etsy_ok": "true"}, {"n": 1, "score": 2}])
    with mock.patch.object(ai.requests, "post", post), mock.patch.object(ai, "_image_part", lambda u: None):
        before = ai.calls
        out = ai.analyze_batch(ads, min_interval=0)
    assert ai.calls - before == 1  # one request for three ads
    assert out[0]["score"] == 2 and out[1] is None and out[2]["score"] == 9 and out[2]["etsy_ok"] is True
    text = "".join(p.get("text", "") for p in sent["body"]["contents"][0]["parts"])
    assert "Объявление №3" in text and "2 € (платное" in text and "Всего объявлений: 3" in text

    def quota(url, params, json, timeout):
        return FakeResp(429, text="Quota exceeded GenerateRequestsPerDay")
    with mock.patch.object(ai.requests, "post", quota):
        try:
            ai.analyze_batch(ads, min_interval=0)
            assert False
        except ai.QuotaExhausted:
            pass


def test_rate_limiter_spacing():
    ai._last_call = 0
    t0 = time.time()
    for _ in range(3):
        ai._wait_turn(0.2)
    assert time.time() - t0 >= 0.39


def test_alive():
    class S:
        def __init__(self, status, text=""):
            self.status_code, self.text = status, text
    cases = {"a": S(410), "https://www.2dehands.be/b": S(200, "Deze advertentie is niet meer beschikbaar"), "c": S(200, "ok"),
             "d": S(403), "https://donnerie.be/annonces/x/": S(200, '<li id="cp_sold"><span>Déjà pris:</span> Oui</li>'),
             "https://donnerie.be/annonces/y/": S(200, "<li>ok</li>")}
    with mock.patch.object(alive, "session") as sess:
        sess.return_value.get.side_effect = lambda url, **kw: cases[url]
        res = {it["url"]: a for it, a in alive.check([{"id": k, "url": k} for k in cases], workers=2)}
    assert res == {"a": False, "https://www.2dehands.be/b": False, "c": True, "d": None,
                   "https://donnerie.be/annonces/x/": False, "https://donnerie.be/annonces/y/": True}, res


def test_full_run():
    """main.run with fake sites, Gemini, Telegram and Firestore: priority, batching, cheap ads, alive check, digest."""
    import main
    from finder import digest, remote, state, telegram
    ads = [Ad("2dehands", "1", "Porseleinen vaas", "u1", location="Gent", posted_at=time.time()),
           Ad("2dehands", "2", "Oud fototoestel", "u2", location="Elsene", posted_at=time.time() - 9000),
           Ad("2dehands", "3", "Gratis kitten", "u3", location="Brussel"),
           Ad("2dehands", "4", "Oude speldjes", "u4", location="Luik", price=3, posted_at=time.time() - 100)]
    settings = json.loads(json.dumps(remote.DEFAULTS))
    settings.update(ai_batch=2, sources={**settings["sources"], "donnerie": {"enabled": False},
                                         "2dehands_cheap": {"enabled": False}})
    batches, tg, saved, marked = [], [], [], []

    def fake_batch(group, **kw):
        batches.append([a.ad_id for a in group])
        return [{"score": 8 if a.ad_id == "2" else 3, "price": "x"} for a in group]
    with mock.patch.object(remote, "load_settings", lambda: settings), \
         mock.patch.object(remote, "start_run", lambda t: "r1"), mock.patch.object(remote, "finish_run", lambda *a: saved.append(a[1])), \
         mock.patch.object(remote, "load_blocked", lambda: (set(), set(), set())), \
         mock.patch.object(remote, "load_feedback_examples", lambda: ""), \
         mock.patch.object(remote, "gemini_used_today", lambda exclude_run=None: 0), \
         mock.patch.object(remote, "save_find", lambda *a, **k: None), mock.patch.object(remote, "progress", lambda *a, **k: None), \
         mock.patch.object(remote, "load_open_finds", lambda s: [{"id": "2dehands_9", "url": "dead"}]), \
         mock.patch.object(remote, "mark_checked", lambda i, a: marked.append((i, a))), \
         mock.patch.object(alive, "is_alive", lambda url: False), \
         mock.patch.object(main.tweedehands, "fetch", lambda src, cats, pages, seen, bids: ads), \
         mock.patch.object(main.ai, "analyze_batch", fake_batch), \
         mock.patch.object(telegram, "send_ad", lambda ad, v, silent: tg.append((ad.ad_id, silent))), \
         mock.patch.object(digest, "maybe_send", lambda *a: tg.append("digest")), \
         mock.patch.object(state, "load", lambda: {"x": 1}), mock.patch.object(state, "save", lambda s: None), \
         mock.patch.object(main.time, "sleep", lambda s: None), \
         mock.patch.dict(os.environ, {"GITHUB_EVENT_NAME": "schedule"}):
        main.run(dry_run=False)
    # kitten dropped by the word filter; Brussels ad first (reachable), then freshest of the rest
    assert batches == [["2", "1"], ["4"]], batches
    assert tg[0] == ("2", False) and tg[-1] == "digest", tg
    assert marked == [("2dehands_9", False)]
    st = saved[-1]
    assert st["status"] == "ok" and st["analyzed"] == 3 and st["junk"] == 1 and st["gone_checked"] == 1, st


def test_digest_due():
    from datetime import datetime, timezone
    from finder import digest
    s = {"digest": {"enabled": True, "hour": 21}}
    assert digest.due(s, datetime(2026, 11, 25, 20, 30, tzinfo=timezone.utc)) == "2026-11-25"  # 21:30 Brussels
    assert digest.due(s, datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)) is None
    assert digest.due({"digest": {"enabled": False}}, datetime(2026, 11, 25, 20, 0, tzinfo=timezone.utc)) is None


def test_price_conf_shown():
    from finder.telegram import format_ad
    data = ai._clean({"score": 7, "price_etsy": "—", "price_ebay": "€5–10", "price_conf": "Низкая (догадка)"})
    assert data["price_conf"] == "низкая"
    assert "уверенность низкая" in format_ad(Ad("2dehands", "1", "Munten", "u"), data)
    assert ai._clean({"score": 1})["price_conf"] == "средняя"





def test_format_and_seller_message():
    from finder.telegram import format_ad, seller_message
    ad = Ad("2dehands", "1", "Vaas <b>", "https://www.2dehands.be/v/x", location="Ukkel", delivery="Ophalen")
    txt = format_ad(ad, {"score": 7, "price": "$20–25", "items": "Boch vaas", "why": "jaren 60", "pickup": "лично"})
    assert "&lt;b&gt;" in txt and "7/10" in txt and "Открыть на 2dehands" in txt and "Hallo!" in txt
    assert seller_message(Ad("2dehands", "2", "Vase ancien", "u", description="Je donne ce vase")).startswith("Bonjour")


def test_vinted_price():
    from finder.telegram import format_ad
    v = ai._clean({"score": 7, "price_etsy": "—", "price_ebay": "€20–30", "price_vinted": "€15–20",
                   "query_en": "Levi's 501 jeans vintage", "query_local": "Levi's 501 jean", "etsy_ok": False})
    assert v["price_vinted"] == "€15–20" and "Vinted €15–20" in v["price"]
    txt = format_ad(Ad("2dehands", "1", "Levi's 501", "u"), v)
    assert "Vinted: €15–20" in txt and "vinted.be/catalog?search_text=Levi%27s+501+jean" in txt
    assert ai._clean({"score": 1})["price_vinted"] == "—"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
