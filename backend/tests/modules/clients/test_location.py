"""The point behind a map link (app.location)."""

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
