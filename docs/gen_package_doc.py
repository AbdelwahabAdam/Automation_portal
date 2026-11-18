"""Writes the package-fields document from the code itself: every live package, the profile its name
resolves to, and the line fields new_sale shows for it, with the labels it shows them under.

The package list is the live catalogue's, one «code<TAB>name» per line. On the server, in /opt/portal:

    sudo docker compose -f docker-compose.prod.yml exec -T db psql -U portal -d portal -t -A -F "$(printf '\t')" \
      -c "select coalesce(code,''), name from packages where is_active order by coalesce(code,'zzz'), name" > packages.tsv

Copy packages.tsv into the backend folder (it holds no client data — package names only). Then, there:
    python ../docs/gen_package_doc.py packages.tsv > ../docs/package_fields.md
"""
import io
import os
import sys
from collections import OrderedDict

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://x:x@localhost/x")
os.environ.setdefault("JWT_SECRET", "a-documentation-run-secret-at-least-32-bytes")
sys.path.insert(0, os.getcwd())

import app.forms  # noqa: E402,F401  registers every form
from app.modules.form_engine import PACKAGE_PROFILES, form_fields, package_fields, package_profile  # noqa: E402

LINE = next(spec for spec in form_fields("new_sale") if spec["type"] == "order_lines")["line_fields"]
STRUCTURAL = {spec["name"] for spec in LINE if spec.get("package_only") or spec.get("open_price_only")}
LABEL = {spec["name"]: spec["label"] for spec in LINE}
# A field is named here as the form names it, with «، إن ينطبق»/«، إن يوجد» left off
SHORT = {name: label.split("،")[0].strip() for name, label in LABEL.items()}


def profile_name(profile):
    if profile is None:
        return "— (no profile: every field, as before)"
    words = " + ".join(profile["match"] + [f"needs {w}" for w in profile.get("needs", [])])
    return f"`{words}`"


def shown(name):
    out = []
    for spec in package_fields(LINE, name):
        if spec["name"] in STRUCTURAL:
            continue
        label = spec["label"].split("،")[0].strip()
        extra = f" ({' / '.join(spec['options'])})" if spec.get("options") != next(
            (s.get("options") for s in LINE if s["name"] == spec["name"]), None) else ""
        renamed = f" ← {SHORT[spec['name']]}" if label != SHORT[spec["name"]] else ""
        out.append(f"{label}{renamed}{extra}")
    return out


rows = [line.rstrip("\n").split("\t") for line in io.open(sys.argv[1], encoding="utf-8") if line.strip()]
groups = OrderedDict()
for code, name in rows:
    profile = package_profile(name)
    key = PACKAGE_PROFILES.index(profile) if profile is not None else len(PACKAGE_PROFILES)
    groups.setdefault(key, []).append((code, name))

w = sys.stdout.write
w("# Package fields — what the order form asks for each package\n\n")
w("Generated from `PACKAGE_PROFILES` in `backend/app/modules/form_engine/options.py` against the live\n")
w("catalogue. Do not edit by hand — change the profiles, then regenerate:\n\n")
w("```sh\ncd backend && python ../docs/gen_package_doc.py packages.tsv > ../docs/package_fields.md\n```\n\n")
w("`packages.tsv` is the live catalogue; the generator's docstring has the command that makes it.\n\n")
w("Every package also has **الكمية (عدد الباقات)**, and a product sold without a fixed price has its\n")
w("price and invoice text. **سعر الكتابة** appears wherever **الكتابة المطلوبة** does.\n\n")
w("A package's name decides its profile: the first one whose words it carries. A package no profile\n")
w("matches keeps every field, exactly as before profiles existed.\n\n")

w("## Profiles\n\n| # | Matches | Fields |\n|---|---|---|\n")
for index, profile in enumerate(PACKAGE_PROFILES, 1):
    fields = shown(groups[index - 1][0][1]) if index - 1 in groups else []
    w(f"| {index} | {profile_name(profile)} | {'، '.join(fields)} |\n")
w(f"| — | anything else | every field: {'، '.join(shown('—'))} |\n\n")

w("## Every package\n\n")
for key in sorted(groups):
    profile = PACKAGE_PROFILES[key] if key < len(PACKAGE_PROFILES) else None
    w(f"### {profile_name(profile)} — {len(groups[key])} package(s)\n\n")
    w(f"Fields: {'، '.join(shown(groups[key][0][1]))}\n\n| Code | Package |\n|---|---|\n")
    for code, name in groups[key]:
        w(f"| {code or '—'} | {name} |\n")
    w("\n")
