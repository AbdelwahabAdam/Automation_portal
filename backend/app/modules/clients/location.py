"""The point behind a map link.

A Google short link («maps.app.goo.gl/…») carries nothing but an id: the place it stands for is
only known once the link is followed. A browser cannot do that — reading where another site
redirects to is not allowed — so the portal follows it here and hands back the point.

Not every link has one. A link shared from a place resolves to «/place/…/@24.1,55.6/…!3d24.1!4d55.6»
and does; one shared from the phone's own position resolves to «?q=<the place's name>&entry=gps» and
does not, because Google kept only the name. Those are answered as "no point in it".
"""

import http.cookiejar
import re
import urllib.error
import urllib.parse
import urllib.request

# Only Google's own map addresses are followed: this takes a link from the person filling the form,
# and a server that fetches whatever it is given can be pointed at things it should not reach
ALLOWED_HOSTS = {"maps.app.goo.gl", "goo.gl", "maps.google.com", "www.google.com", "google.com",
                 "maps.app.google.com"}
MAX_HOPS = 5
TIMEOUT_SECONDS = 10
# «!3d24.1787!4d55.6045» is the place itself; «@24.1787,55.6045,17z» is where the map was centred,
# which is the same spot for a shared place and the better of the two when only it is there
PLACE_POINT = re.compile(r"!3d(-?\d{1,2}(?:\.\d+)?)!4d(-?\d{1,3}(?:\.\d+)?)")
MAP_CENTRE = re.compile(r"@(-?\d{1,2}(?:\.\d+)?),(-?\d{1,3}(?:\.\d+)?)")
PLAIN_POINT = re.compile(r"[?&]q=(-?\d{1,2}(?:\.\d+)?),\s*(-?\d{1,3}(?:\.\d+)?)")


class NotALocation(Exception):
    """The link is not one we follow, or holds no point once followed."""


def host_of(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").lower()


def allowed(url: str) -> bool:
    return urllib.parse.urlsplit(url).scheme in ("http", "https") and host_of(url) in ALLOWED_HOSTS


def point_in(url: str) -> tuple[float, float] | None:
    """The point a map address holds, if it holds one. Tried in order of how exact each is."""
    for pattern in (PLAIN_POINT, PLACE_POINT, MAP_CENTRE):
        found = pattern.search(url or "")
        if not found:
            continue
        lat, lng = float(found[1]), float(found[2])
        if abs(lat) <= 90 and abs(lng) <= 180:
            return lat, lng
    return None


class _KeepRedirects(urllib.request.HTTPRedirectHandler):
    """Stops at each hop so the address can be checked before it is followed."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed(newurl):
            raise NotALocation(f"redirected away from Google's maps: {host_of(newurl)}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def resolve(url: str) -> tuple[float, float]:
    """The point a link stands for, following it when it is a short one. Raises NotALocation."""
    url = (url or "").strip()
    if not allowed(url):
        raise NotALocation("رابط غير معروف. استخدم رابط خرائط Google أو اختر الموقع على الخريطة.")
    here = point_in(url)
    if here:
        return here

    opener = urllib.request.build_opener(_KeepRedirects(),
                                         urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    request = urllib.request.Request(url, headers={
        # Google answers a plain request with a page that has no point in it
        "User-Agent": "Mozilla/5.0 (compatible; FutureLifePortal/1.0)",
        "Accept-Language": "en",
    })
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as answer:
            final = answer.geturl()
    except NotALocation:
        raise
    except (urllib.error.URLError, OSError) as error:
        raise NotALocation(f"تعذّر فتح الرابط: {error}") from error

    found = point_in(final)
    if not found:
        # Shared from the phone's own position: Google kept the place's name and not where it is
        raise NotALocation("هذا الرابط لا يحمل إحداثيات. اختر الموقع على الخريطة.")
    return found
