"""Everything the portal does outside a page: the nightly sync, the admin page's buttons, and
the command-line imports.

    python -m app.jobs --list                list every job
    python -m app.jobs sync_clients          run one

Importing this registers every job. A job holds no business rules of its own — it calls a
module's service — so the page, the cron and the command line all run the same code, and every
run is recorded in `job_runs`.
"""

from . import (create_user, fake_daftra, import_catalog, import_client_categories,
               import_maintenance_items, import_product_images, redraw_work_orders, sync_clients,
               sync_products, warm_daftra_cache)
from .models import JobRun
from .registry import all_jobs, find, get, job, names, on_admin_page
from .router import router
from .runner import run_now, start_in_background

# The modules that register the jobs, so importing this package is enough
JOBS = (sync_clients, sync_products, warm_daftra_cache, import_catalog, import_client_categories,
        import_maintenance_items, import_product_images, redraw_work_orders, create_user, fake_daftra)

__all__ = ["JOBS", "JobRun", "all_jobs", "find", "get", "job", "names", "on_admin_page", "router",
           "run_now", "start_in_background"]
