from copy import deepcopy
from datetime import date
from refresh_portaltickets_editorial import make_event, parse_detail_markup, apply_detail, refresh_dataset


def sample():
    return make_event("EXTINCIÓN TOTAL VOL.1", date(2026, 9, 26), "20:00", "Espacio Barcelona", "Valparaíso",
                      "https://www.portaldisc.com/evento/extinciontotal1")


def test_detail_copies_event_poster_from_already_fetched_page():
    detail = parse_detail_markup('''<meta content="https://images.portaldisc.com/l/eventos/360/22009.jpg" property="og:image">
        <img id="imgdisco" src="https://images.portaldisc.com/eventos/22009.jpg">''')
    event = apply_detail(sample(), detail, verified_at="2026-09-23T10:00:00-03:00")
    assert event["image"]["url"] == "https://images.portaldisc.com/eventos/22009.jpg"
    assert event["image"]["relevance"] == "event_specific"


def test_refresh_preserves_exact_event_image_when_detail_is_unavailable():
    previous = sample()
    previous["image"] = {"url": "./assets/event-images/valpo/verified.webp", "cache": {"sha256": "abc"}}
    result, _ = refresh_dataset({"events": [previous]}, [sample()], fetch_ok=True)
    assert result["events"][0]["image"] == previous["image"]
    other = sample()
    other["source_url"] += "-other"
    result, _ = refresh_dataset({"events": [previous]}, [other], fetch_ok=True)
    assert result["events"][0]["image"]["url"] is None


def test_no_logo_or_arbitrary_image_is_promoted():
    detail = parse_detail_markup('<meta property="og:image" content="/images/logo_portaltickets.png"><img src="/other-event.jpg">')
    assert detail["image_url"] is None
