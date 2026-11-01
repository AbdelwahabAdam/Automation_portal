"""The point behind a map link (app.location)."""

import io
import json
import urllib.error

import pytest

from app.modules.clients import location

# The address a Google short link resolves to, in the two shapes the real ones take
A_PLACE = ("https://www.google.com/maps/place/Giza+Necropolis/@29.9772223,31.1322659,21z/"
           "data=!4m6!3m5!1s0x14584f7de239bbcd:0xca7474355a6e368b!8m2!3d29.9772962!4d31.1324955")
FROM_GPS = ("https://www.google.com/maps?q=KINGDOM+GYM,+Al+Haram,+Giza+Governorate+3510262"
            "&ftid=0x14584f000fdaa881:0xdb8b292e8df8603d&entry=gps&g_st=ic")


def test_a_place_gives_the_place_itself_not_where_the_map_was_centred():
    # «!3d…!4d…» is the place; «@…» a few metres away is only where the view sat
    assert location.point_in(A_PLACE) == (29.9772962, 31.1324955)


def test_a_link_the_map_wrote_is_read_without_following_it():
    assert location.point_in("https://www.google.com/maps?q=24.178700,55.604510") == (24.1787, 55.60451)


def test_a_link_shared_from_the_phones_own_position_holds_no_point():
    assert location.point_in(FROM_GPS) is None


def test_nonsense_holds_no_point():
    assert location.point_in("https://www.google.com/maps/place/Somewhere") is None
    assert location.point_in("") is None


@pytest.mark.parametrize("url", [
    "https://evil.example.com/maps?q=1,2",          # not Google's
    "file:///etc/passwd",                            # not even a web address
    "http://169.254.169.254/latest/meta-data/",      # the machine asking itself for its secrets
    "https://google.com.evil.example/maps?q=1,2",    # a host that only looks like Google's
])
def test_only_googles_own_map_addresses_are_followed(url):
    assert not location.allowed(url)
    with pytest.raises(location.NotALocation):
        location.resolve(url)


def test_a_short_link_is_followed_to_its_point(monkeypatch):
    """The point only shows up once the link has been followed, which is the server's job."""
    class Answer:
        def geturl(self):
            return A_PLACE

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(location.urllib.request.OpenerDirector, "open", lambda *a, **k: Answer())
    assert location.resolve("https://maps.app.goo.gl/GGCuVgNY1iFT6Ahx5") == (29.9772962, 31.1324955)


def test_a_link_with_no_point_says_so_rather_than_guessing(monkeypatch):
    class Answer:
        def geturl(self):
            return FROM_GPS

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(location.urllib.request.OpenerDirector, "open", lambda *a, **k: Answer())
    with pytest.raises(location.NotALocation, match="إحداثيات"):
        location.resolve("https://maps.app.goo.gl/GQHpiS558z2DLsuG7?g_st=ic")


def google_knows(monkeypatch, final=FROM_GPS, places=None, refused=False, key="test-key"):
    """A short link landing on `final`, and what the Places API answers; the searches sent are returned."""
    searches = []

    class Followed:
        def geturl(self):
            return final

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def search(request, *args, **kwargs):
        searches.append(request)
        if refused:
            raise urllib.error.HTTPError(request.full_url, 403, "billing is off", {}, None)
        return io.BytesIO(json.dumps({"places": places} if places else {}).encode())

    monkeypatch.setattr(location.urllib.request.OpenerDirector, "open", lambda *a, **k: Followed())
    monkeypatch.setattr(location.urllib.request, "urlopen", search)
    monkeypatch.setattr(location.settings, "google_maps_api_key", key)
    return searches


AJMAN = [{"location": {"latitude": 25.4052, "longitude": 55.5136}}]


def test_a_link_from_the_phones_position_asks_google_where_the_place_is(monkeypatch):
    searches = google_knows(monkeypatch, places=AJMAN)
    assert location.resolve("https://maps.app.goo.gl/GQHpiS558z2DLsuG7?g_st=ic") == (25.4052, 55.5136)
    [search] = searches
    sent = json.loads(search.data)
    assert search.full_url == "https://places.googleapis.com/v1/places:searchText"
    assert sent["textQuery"] == "KINGDOM GYM, Al Haram, Giza Governorate 3510262"
    assert sent["locationRestriction"] == location.UAE
    assert search.get_header("X-goog-api-key") == "test-key"
    assert search.get_header("X-goog-fieldmask") == "places.location"


def test_a_link_holding_its_own_point_is_not_paid_for(monkeypatch):
    searches = google_knows(monkeypatch, final=A_PLACE, places=AJMAN)
    assert location.resolve("https://maps.app.goo.gl/GGCuVgNY1iFT6Ahx5") == (29.9772962, 31.1324955)
    assert searches == []


def test_without_a_key_google_is_not_asked(monkeypatch):
    searches = google_knows(monkeypatch, places=AJMAN, key="")
    with pytest.raises(location.NotALocation, match="إحداثيات"):
        location.resolve("https://maps.app.goo.gl/GQHpiS558z2DLsuG7?g_st=ic")
    assert searches == []


def test_a_name_google_cannot_find_in_the_emirates_is_left_to_be_typed_in(monkeypatch):
    google_knows(monkeypatch)
    with pytest.raises(location.NotALocation, match="إحداثيات"):
        location.resolve("https://maps.app.goo.gl/GQHpiS558z2DLsuG7?g_st=ic")


def test_google_refusing_is_a_link_with_no_point_not_a_crash(monkeypatch):
    google_knows(monkeypatch, refused=True)
    with pytest.raises(location.NotALocation, match="إحداثيات"):
        location.resolve("https://maps.app.goo.gl/GQHpiS558z2DLsuG7?g_st=ic")


def test_an_address_with_no_name_in_it_is_not_searched_for(monkeypatch):
    searches = google_knows(monkeypatch, final="https://www.google.com/maps/place/Somewhere", places=AJMAN)
    with pytest.raises(location.NotALocation):
        location.resolve("https://maps.app.goo.gl/GQHpiS558z2DLsuG7?g_st=ic")
    assert searches == []
