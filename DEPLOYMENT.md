# CRMS — Deployment Guide

Call Records Management System — a Frappe v15 app for importing operator CDRs,
managing working numbers / cases, and running CDR analytics (reports, movement
map, common-numbers link graph, PDF report packs).

---

## 1. Prerequisites

### System (once per server)
- **Frappe Bench** with **Frappe v15** and **Python 3.10+** (the app targets `>=3.10`).
- **MariaDB 10.6+** (the reports use CTEs / window functions).
- **wkhtmltopdf 0.12.x _with patched Qt_** — required for the PDF exports
  (report PDFs, the "Report Pack" ZIP, and the network-graph PDF). A standard
  `bench init` installs the patched build; verify with:
  ```bash
  wkhtmltopdf --version        # must say "(with patched qt)"
  ```
  If it does not, install the patched binary from
  <https://github.com/wkhtmltopdf/packaging/releases> (do **not** use the plain
  distro `apt install wkhtmltopdf` — it lacks the patch and breaks page sizing).
- **Node / yarn** on the bench (for `bench build`) — already present on any bench.

### Python packages
Declared in `pyproject.toml` and installed automatically by `bench get-app` /
`bench install-app` (via pip). The only external one is:
- `openpyxl` — reads `.xlsx` CDR files (also ships with Frappe).

No other third-party Python packages are used; everything else is the standard
library or Frappe itself.

> **Note:** Frappe apps declare dependencies in `pyproject.toml`, not
> `requirements.txt`. `bench get-app` / `install-app` install them for you. To
> (re)install this app's Python **and** Node prerequisites explicitly at any time:
> ```bash
> bench setup requirements --app crms
> ```

### Frontend library
- **Cytoscape.js** (the link-graph engine) is **vendored** in the repo at
  `crms/public/js/cytoscape.min.js` — no CDN, works fully offline. It just needs
  `bench build` to be served (see below).

---

## 2. Install on a new site

```bash
# from the bench directory
bench get-app https://github.com/mamirbalouch/crms_frappe.git   # or a local path
bench --site <yoursite> install-app crms
bench build --app crms
bench --site <yoursite> clear-cache
bench restart
```

`install-app` runs the `after_install` hook, which **seeds** the Mobile
Operators, Call Types, and the 18 built-in CDR Import Profiles automatically.

---

## 3. Update an existing site (new version)

```bash
cd apps/crms && git pull && cd ../..
bench --site <yoursite> migrate      # applies doctypes/reports/pages + re-seeds
bench build --app crms               # REQUIRED — rebuilds JS incl. Cytoscape
bench --site <yoursite> clear-cache
bench restart
```

> **`bench build` is not optional in production.** In development a file-watcher
> rebuilds assets for you; production serves pre-built assets, so a skipped build
> is the #1 cause of "the page/graph looks broken after deploy." If in doubt,
> run it and hard-refresh the browser (Ctrl+Shift+R).

`migrate` runs the `after_migrate` hook (`crms.setup.seed_initial_data`), which
is **idempotent** and keeps the baseline master data / import profiles in sync.

---

## 4. Production settings

- **`developer_mode` must be OFF** (the default). Only enable it on a dev bench.
  Check with:
  ```bash
  bench --site <yoursite> execute "frappe.conf.get('developer_mode')"
  ```
- The app ships all doctype/report/page definitions as files, so `migrate`
  applies them without developer mode.
- Realtime (`socketio`) is proxied by nginx in production — the
  `127.0.0.1:9000/socket.io` CORS message seen on a raw dev server does not
  occur behind nginx. Regenerate nginx config if needed:
  `bench setup nginx && sudo service nginx reload`.

---

## 5. Post-deploy smoke test (~2 minutes)

Open the **CRMS** workspace and check:

1. **CDR Bulk Import** — import one `.xlsx`/`.csv` file; open the created Call
   Record and confirm the CDR rows loaded.
2. **Call Detail Record Report** → **Download PDF** (tests wkhtmltopdf).
3. **CDR Report Pack** → pick a Case Project → **Generate All Reports (ZIP)**.
4. **Common Numbers Network** → **Show Network** (graph draws) → **Export PDF**.
5. **CDR Movement Map** → pick a Working Number → **Show Movement**.

If an asset-dependent page (network graph, movement map) looks blank, it is
almost always a missed `bench build` — re-run it and hard-refresh.

---

## 6. Feature-specific notes

- **CDR Import Profiles are re-synced on every `migrate`.** Editing a *shipped*
  profile via the UI will be overwritten on the next migrate. Custom profiles
  (created with a different name, e.g. via "Save mapping as a new profile") are
  never touched. To permanently change a shipped profile, duplicate it under a
  new name.
- **Excel format:** only `.xlsx` (and `.csv`) are supported. Legacy `.xls`
  returns a clear "save as .xlsx" message.
- **Working Number naming:** the record name is the normalized mobile number
  (e.g. `3137760580`), qualified with the Case Project only on a genuine
  cross-case collision (`3137760580-CP0002`). Case Projects are named `CP0001`,
  `CP0002`, …
- **PDF/ZIP files** created by the report exports are stored as private Files.
  On a busy site consider a periodic cleanup of old export Files.
- **Link graph & Frappe:** the Common Numbers Network runs Cytoscape inside a
  same-origin iframe on purpose — the Frappe desk locks `Array.prototype.move`
  (read-only), which crashes Cytoscape if it loads in the main page. The iframe
  gives it a clean realm. This is client-side only; nothing to configure on the
  server beyond building the vendored asset.

---

## 7. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Network graph or movement map is blank | `bench build --app crms` was not run, or browser cache — build + hard-refresh. |
| PDF exports fail or are mis-sized | wkhtmltopdf missing or not the patched-Qt build — see §1. |
| Reports/pages missing after deploy | `bench --site <site> migrate` not run. |
| No operators / call types / profiles | Seed didn't run — `bench --site <site> execute crms.setup.seed_initial_data`. |
| Excel import says openpyxl missing | `bench pip install openpyxl` (normally auto-installed). |
