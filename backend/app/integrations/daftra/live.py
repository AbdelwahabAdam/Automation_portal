"""The live Daftra account, over HTTP: the calls, their retries, Daftra's own error messages,
the file upload and the invoice PDF.

`fake.py` offers the same three functions — `call`, `upload_file` and `invoice_pdf` — without a
network, and `client.py` picks between the two. Nothing above them knows which it got.
"""

import http.cookiejar
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid

from ...core.config import settings
from .errors import DaftraError, NotFound

TIMEOUT_SECONDS = 20
# Daftra (or the way to it) briefly unavailable: worth asking again
RETRY_STATUSES = {502, 503, 504}


def _error_message(raw: bytes) -> str:
    """Daftra's own explanation of a refused call, e.g. which field it did not accept."""
    try:
        body = json.loads(raw)
    except ValueError:
        return raw.decode("utf-8", "replace")[:300]
    if not isinstance(body, dict):
        return str(body)[:300]
    parts = [str(body.get("message") or "")]
    for key in ("validation_errors", "errors"):
        if body.get(key):
            parts.append(json.dumps(body[key], ensure_ascii=False))
    return " — ".join(part for part in parts if part)[:500] or json.dumps(body, ensure_ascii=False)[:300]


def call(method: str, path: str, params: dict | None = None, body: dict | list | None = None) -> dict:
    """path starts at the account's address, e.g. "/api2/invoices.json"."""
    if not settings.daftra_subdomain or not settings.daftra_api_key:
        raise DaftraError("Daftra is not configured")
    url = f"https://{settings.daftra_subdomain}.daftra.com{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Accept": "application/json", "apikey": settings.daftra_api_key}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    # A read that fails on the way (network, timeout, Daftra briefly unavailable) is tried once more;
    # a write is not, since it may have been saved even though no answer came back
    attempts = 2 if method == "GET" else 1
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code in RETRY_STATUSES and attempt < attempts:
                continue
            message = _error_message(error.read())
            raise (NotFound if error.code == 404 else DaftraError)(f"HTTP {error.code}: {message}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt < attempts:
                continue
            raise DaftraError(str(error)) from error
        except ValueError as error:
            raise DaftraError(str(error)) from error


def _file_body(filename: str, content_type: str, content: bytes) -> tuple[str, bytes]:
    """The multipart body Daftra's upload takes: one part, named "file"."""
    boundary = "----portal" + uuid.uuid4().hex
    # A quote or newline in the name would break the part's own header
    name = re.sub(r'["\r\n]', "", filename or "") or "file"
    head = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
            f'Content-Type: {content_type or "application/octet-stream"}\r\n\r\n').encode("utf-8")
    return boundary, head + content + f"\r\n--{boundary}--\r\n".encode("utf-8")


def upload_file(content: bytes, filename: str, content_type: str,
                entity: str = "invoice", field: str = "invoices.documents") -> int:
    """Puts a file in the account's file store and returns its id.

    That id is what both an invoice's attachment and a work order's صورة المنتج take: product
    images, work-order uploads and invoice documents share one table in Daftra. Not in Daftra's
    docs — the account's own UI uses this address, and it accepts our API key.
    """
    if not settings.daftra_subdomain or not settings.daftra_api_key:
        raise DaftraError("Daftra is not configured")
    boundary, body = _file_body(filename, content_type, content)
    url = f"https://{settings.daftra_subdomain}.daftra.com/v2/api/entity/upload_file/{entity}/{field}"
    request = urllib.request.Request(url, data=body, method="POST", headers={
        "Accept": "application/json", "apikey": settings.daftra_api_key,
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "X-Requested-With": "XMLHttpRequest",  # as the account's own UI sends it
    })
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS * 3) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        raise DaftraError(f"HTTP {error.code}: {_error_message(error.read())}") from error
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        raise DaftraError(str(error)) from error
    if not result.get("id"):
        raise DaftraError(f"Daftra did not return a file id: {json.dumps(result, ensure_ascii=False)[:300]}")
    return int(result["id"])


def invoice_pdf(invoice_id: int, pdf_url: str) -> bytes:
    """The invoice's PDF, as Daftra prints it.

    invoice_pdf_url does not return the file: its "hash" signs the visitor in to the client view
    of that invoice (a session cookie) and redirects there. The PDF is then served at
    /client/invoices/view/<id>.pdf within that session.
    """
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    try:
        opener.open(pdf_url, timeout=TIMEOUT_SECONDS).read()
        url = f"https://{settings.daftra_subdomain}.daftra.com/client/invoices/view/{invoice_id}.pdf"
        with opener.open(url, timeout=TIMEOUT_SECONDS * 3) as response:
            content = response.read()
    except (urllib.error.URLError, TimeoutError) as error:
        raise DaftraError(str(error)) from error
    if not content.startswith(b"%PDF"):
        raise DaftraError("Daftra did not return a PDF for the invoice")
    return content
