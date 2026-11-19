import os
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# The Daftra subdomain and API key live in the workspace-level .env (keys: subdomain, apikey);
# that folder does not exist once the backend runs from a Docker image, hence the length check.
# Anchored on the backend folder, not on this file's depth, so moving this file does not move
# the uploads or make the portal read a different .env.
_APP = Path(__file__).resolve().parent.parent
BACKEND_DIR = _APP.parent
WORKSPACE_ENV = BACKEND_DIR.parents[1] / ".env" if len(BACKEND_DIR.parents) > 1 else _APP / ".env"
# Request attachments, one folder per request (UPLOAD_DIR moves them, e.g. for the tests)
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR") or BACKEND_DIR / "uploads")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(WORKSPACE_ENV, ".env"), env_file_encoding="utf-8-sig", extra="ignore")

    database_url: str
    jwt_secret: str
    jwt_expire_minutes: int = 60 * 12
    # On: nothing reaches Daftra; a stand-in inside the portal answers instead, so the whole flow
    # can be tried locally without touching the live account (see the README's "Run"). The default
    # here is off; docker-compose.yml turns it on locally, and the production file hard-codes it off.
    daftra_fake: bool = False
    daftra_subdomain: str = Field("", validation_alias=AliasChoices("daftra_subdomain", "subdomain"))
    daftra_api_key: str = Field("", validation_alias=AliasChoices("daftra_api_key", "apikey"))
    # Ids in our Daftra account used on every invoice an approved new sale creates
    daftra_store_id: int = 1
    daftra_branch_id: int = 1
    # Marks the invoice, payment and work order a request made, so a retry finds them instead of
    # making them twice. It must differ between portals sharing one Daftra account: a test portal
    # numbers its requests from 1 too, and its «PORTAL-12» would otherwise be taken for this one's.
    daftra_marker_prefix: str = "PORTAL"
    # "VAT Included" (5%): our prices already include VAT
    daftra_tax_id: int = 3
    # The "service" product an inscription is invoiced as, with its text as the line's description
    daftra_inscription_product_id: int = 194
    # "exchange contract": the one line of a maintenance contract renewal invoice
    daftra_renewal_product_id: int = 37
    # File id for the work order's صورة المنتج (field_30). Daftra requires that field and treats it
    # as a file: text in it makes the save answer 500 and the work order's التفاصيل tab error. The
    # portal cannot upload, so it points every work order at one image uploaded there by hand.
    daftra_work_order_image_id: int = 16412
    # Who every work order is assigned to under معلومات الموظفين المعينين: «السيد محمد حسان #2», the
    # staff member the installations are held by. The same one whoever sent the request, so the
    # technical department always finds its work in one place. A setting, not a constant: the
    # person changes without the portal changing.
    daftra_work_order_staff_id: int = 2
    # Off: the إثبات الدفع is not sent to the invoice in Daftra. Both calls it needs are proven
    # against the live account (see daftra-api.md 4a); set DAFTRA_SEND_PAYMENT_PROOF=true to turn on.
    daftra_send_payment_proof: bool = False
    # Keys of the client custom fields Daftra requires on a new client: اسم الجهاز and Coordinates
    daftra_client_device_field: str = "test"
    # The اسم الجهاز every new client gets (Nabaa + food cooler); the form does not ask for it
    daftra_default_device_name: str = "N + F"
    # The staff member Daftra records as the maker of whatever the API makes without one of its own.
    # A payment made through the API always carries it: Daftra drops the staff_id (and the notes)
    # the portal sends with a payment, as every payment it made on the live account shows.
    daftra_api_staff_id: int = -3
    # How long an approval waits before sending a payment again that Daftra left unanswered, unless
    # the payment shows up on the invoice first. Daftra recorded one about a minute after it was
    # sent, well after the portal had stopped waiting (TIMEOUT_SECONDS), so twice that. 0: no wait.
    daftra_unanswered_payment_wait_seconds: int = 120
    # The work order status (follow_up_status, item_type 8) a work order for a back door starts in:
    # «ابواب» on our account. Found by name in GET /v2/api/entity/follow_up_status/list/1?page=N.
    daftra_work_order_door_status_id: int = 107
    # …and a حفظ الطعام food cooler's (FLP-023/024), whichever cover it has: «برادة طعام بكفر نبع المزن»
    daftra_work_order_food_cooler_status_id: int = 198
    # …and the one a نبع المزن or سقيا الخير cooler's work order starts in, by the form's الإمارة (its
    # own spelling, forms.options.EMIRATES). An emirate not here starts in Daftra's own first status.
    # As JSON in DAFTRA_WORK_ORDER_COOLER_STATUS_BY_EMIRATE to change it.
    daftra_work_order_cooler_status_by_emirate: dict[str, int] = {
        "أبوظبي": 5,        # نبع المزن + سقيا الخير ابوظبي
        "العين": 2,         # نبع المزن + سقيا الخير العين
        "دبي": 6,           # نبع المزن + سقيا الخير دبي
        "رأس الخيمة": 187,  # برادات نبع المزن + سقيا الخير راس الخيمه
    }
    daftra_client_coordinates_field: str = "coordinates_text"
    # Empty: a map link shared from a phone's own position leaves الإحداثيات to be typed in. Set: Google's
    # Places API is asked where the place it names is, which Google bills per call (clients/location.py).
    google_maps_api_key: str = ""
    # Which version is running, written into the image when it is built (see backend/Dockerfile).
    # app_version is the number in the VERSION file; app_build counts the commits behind it.
    app_version: str = "dev"
    app_build: str = "0"
    app_commit: str = ""
    app_built_at: str = ""
    # Address of the portal as users open it; used for the links sent by email
    public_url: str = "http://localhost:5174"
    password_link_hours: int = 72
    # Admins always log in with a code sent to their email after the password
    require_admin_mfa: bool = True
    # Email is off until smtp_host and mail_from are set
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True
    mail_from: str = ""


settings = Settings()
