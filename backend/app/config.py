import os
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# The Daftra subdomain and API key live in the workspace-level .env (keys: subdomain, apikey);
# that folder does not exist once the backend runs from a Docker image, hence the length check.
_HERE = Path(__file__).resolve()
WORKSPACE_ENV = _HERE.parents[3] / ".env" if len(_HERE.parents) > 3 else _HERE.parent / ".env"
# Request attachments, one folder per request (UPLOAD_DIR moves them, e.g. for the tests)
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR") or _HERE.parent.parent / "uploads")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(WORKSPACE_ENV, ".env"), env_file_encoding="utf-8-sig", extra="ignore")

    database_url: str
    jwt_secret: str
    jwt_expire_minutes: int = 60 * 12
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
    # Off: the إثبات الدفع is not sent to the invoice in Daftra. Both calls it needs are proven
    # against the live account (see daftra-api.md 4a); set DAFTRA_SEND_PAYMENT_PROOF=true to turn on.
    daftra_send_payment_proof: bool = False
    # Keys of the client custom fields Daftra requires on a new client: اسم الجهاز and Coordinates
    daftra_client_device_field: str = "test"
    # The اسم الجهاز every new client gets (Nabaa + food cooler); the form does not ask for it
    daftra_default_device_name: str = "N + F"
    daftra_client_coordinates_field: str = "coordinates_text"
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
