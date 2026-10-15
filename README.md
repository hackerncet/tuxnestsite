# NCET VerifyFlow — AI-Powered Document Verification and Approval

A database-backed, role-enforced, AI-assisted college document-verification application prepared for **Nagarjuna College of Engineering and Technology (NCET), Bengaluru**. The interface uses the two institution logos supplied for this project. This is an **independent, deployment-ready implementation**, not a claim of official college endorsement, finished security accreditation, or a currently live Render service.

## Architecture

| Component | Technology |
|---|---|
| UI | Responsive HTML, CSS and vanilla JavaScript, with no frontend framework/runtime dependency |
| API | Python 3.13, FastAPI, SQLAlchemy 2, Alembic |
| Database | PostgreSQL on Render or college-operated Postgres; SQLite for development/tests |
| Document analysis | PyMuPDF for PDFs, python-docx for DOCX, Tesseract OCR for scanned pages/images |
| Rule evaluator | Deterministic checks plus OpenRouter `google/gemma-4-31b-it:free` for language/semantic verification |
| Background processing | Separate Python polling worker, storing queue state and immutable report snapshots in Postgres |
| File storage | Private PostgreSQL bytes by default; supported private S3/R2 or persistent disk alternatives |
| Authentication | Argon2id password hashes, HttpOnly sessions, CSRF defense, login throttling, server-side role/department enforcement |
| Secrets | API key encrypted with Fernet before storage; encryption key kept outside the DB, in Render/server secrets |

**Never commit `.env` or real API keys.** Passwords supplied for the earlier frontend-only demonstration are **not valid** for this backend and are **not reused**. There are no seeded documents or hardcoded live users.

## Access and workflow

- **Super Admin** — Creates, deactivates, and resets passwords for Staff, HOD, Principal and IQAC accounts; manages the encrypted OpenRouter key; reads the audit history. Initial administrator created once through an environment secret.
- **HOD** — Builds, edits and publishes departmental rulebooks (mandatory headings, phrases, page counts, date, signatures, formatting, writing quality, semantic guidance). Every published version is retained. Reviews documents for their department and approves or rejects with feedback.
- **Staff** — Uploads PDF, DOCX, TXT, PNG or JPG up to 10 MB, monitors verification, reviews rule-by-rule findings with location and correction guidance, and resubmits corrected versions. Every revision is retained.
- **Principal / IQAC** — View and download **only documents that the HOD has approved**. Neither role has authority to publish rulebooks or manage users.

On submission the document enters **Verifying**. The worker runs extraction and deterministic checks before calling OpenRouter with the *document content and the HOD policy version bound to that submission*. Verified documents enter **Pending HOD Approval**. Confirmed mandatory failures enter **Needs Correction**. Missing rules, unavailable AI/OCR, incomplete analysis and low-confidence interpretations enter **Manual Review** and cannot be silently auto-passed or auto-rejected. Final approval is always human HOD action, not AI action. After approval, Principal and IQAC can see the record.

**External processing notice:** Configuring OpenRouter and submitting a document can send document text to an external model provider. Obtain institutional authorization, review provider privacy/retention terms, and do not upload confidential student or staff information until approved. Document text is treated as untrusted input, not executable instructions.

### AI model behavior and limits

The configured OpenRouter model ID is `google/gemma-4-31b-it:free` (advertised context **262,144 tokens**). The integration asks for JSON objects, then locally validates the response structure, cited rule IDs, result values, and confidence. The provider does **not** guarantee schema-enforced JSON. Free model capacity and availability can fluctuate; outages route to **Manual Review**. To control costs, latency and output reliability the application limits extracted input to **110,000 characters**, supports at most **120 PDF pages**, and performs OCR on at most **35 pages** per PDF. Incomplete text extraction never earns an automatic pass. DOCX pagination and signature verification may require human confirmation; this is not a forensic signature-validation or pixel-perfect typography engine. Legacy `.doc` is not supported; convert to `.docx` or PDF.

## Quick local start (development)

Requires Python 3.13, Tesseract `tesseract-ocr` / `tesseract-ocr-eng`, and (optionally) PostgreSQL. Start in the root directory:

```bash
python -m venv .venv
source .venv/bin/activate                     # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
export APP_ENV=development
export DATABASE_URL=sqlite:///./ncet-dev.sqlite3
export SETTINGS_ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())')"
export NCET_BOOTSTRAP_ADMIN_PASSWORD='YOUR_NEW_STRONG_UNIQUE_PASSWORD_HERE'
alembic upgrade head
python -m app.bootstrap
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000/app** and log in with user `admin` and the password you set. Go to **Super Admin → Users** to create HOD/Staff/Principal/IQAC users and **Integrations** to enter your OpenRouter key. With no key, reports fall back to Manual Review rather than making up AI results.

The verifier runs as a **second process**; without it uploads remain in the Verifying queue:

```bash
python -m app.worker
```

## Deploy to Render (existing database, one web service)

The project now ships a **single-web-service** Render Blueprint using an **existing**
PostgreSQL database, so it will not create another paid database. The selected free
Oregon plan is suitable only for a low-traffic pilot, because idle web services sleep,
interrupting document-verification work.

1. Connect the `main` branch of this repo to a new Render Docker web service or
   import `render.yaml` as a Blueprint. Select region **Oregon**, root directory `.`.
2. Set `DATABASE_URL` privately in Render. Use an **internal URL** if PostgreSQL is
   in the *same* workspace and region; for an externally connected Render database,
   set the external PostgreSQL URL with `sslmode=require` for TLS.
3. Generate and set `SETTINGS_ENCRYPTION_KEY` (a valid Fernet key), and a strong
   one-time `NCET_BOOTSTRAP_ADMIN_PASSWORD`. Do not reuse public demo credentials.
4. Set `PUBLIC_ORIGIN` to the exact HTTPS Render URL (no trailing slash),
   `APP_ENV=production`, `STORAGE_BACKEND=database`, and
   `APP_RUN_WORKER_IN_WEB=true`.
5. Deploy. The startup runs Alembic migrations, bootstraps the initial `admin` user
   if absent, and starts the API and worker processes together. Verify `/healthz`,
   then sign in at `/app` and configure users, HOD rules and the OpenRouter API key.
6. Before serving real institutional data, move to always-on compute (preferably
   a separate worker), implement malware scanning and backups, monitor failures,
   rotate exposed database credentials, and secure permission to transmit documents
   to OpenRouter. `SCAN_MODE=off` is not suitable for untrusted production uploads.

## Self-hosting on a college-provided server

For a Linux server with Docker Compose installed, use **`compose.yaml`** and a private `.env` defining `POSTGRES_PASSWORD`, `NCET_BOOTSTRAP_ADMIN_PASSWORD`, `SETTINGS_ENCRYPTION_KEY`, and `PUBLIC_ORIGIN`. Set `APP_ENV=production`. Use a dedicated reverse proxy for valid HTTPS, make regular encrypted backups of the PostgreSQL volume, restrict SSH/firewall access, and do not expose the PostgreSQL port publicly. The web service binds to `127.0.0.1:8000` on the server so it is reachable only through local access or your reverse proxy. Generate a URL-safe DB password (for example, hexadecimal) because it is embedded in a database URL.

```bash
docker compose --env-file .env up --build -d
docker compose ps
curl http://127.0.0.1:8000/healthz
```

If using a college-managed external PostgreSQL service instead, run the Dockerfile's web and worker processes separately with the same `DATABASE_URL`, and provide reliable storage/backups. The web command applies Alembic migrations and initializes only explicitly provisioned accounts; the worker must also be running for AI jobs to complete.

### Storage options

The default PostgreSQL binary storage guarantees that web/worker deployments see identical file contents across instances, with no ephemeral filesystem dependency. For larger institutions, configure **private S3/R2** bucket storage via `STORAGE_BACKEND=s3`, `S3_BUCKET`, `S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and `S3_REGION`; serve attachments exclusively through server permission checks. Persistent-disk mode requires a true persistent mount and prevents easy horizontal scaling. Do not enable `disk` on Render free ephemeral storage.

### Production gates and limitations

- A successful local integration test suite is not a substitute for real Render staging smoke tests, a pen test, disaster-recovery rehearsal, or institutional acceptance testing.
- Source logos were provided by the user; permission to represent the institution officially must be confirmed.
- PDF OCR may require manual inspection of poorly scanned handwriting/stamps and signatures; this is a document review aide, not legal/forensic certification.
- For highly sensitive records, ensure the chosen external model provider is contractually authorized or swap in an institution-controlled inference provider.
- Configure optional ClamAV (`SCAN_MODE=clamav`, `CLAMAV_HOST`, `CLAMAV_PORT`); when enabled, scanning failures must block uploads. The default `SCAN_MODE=off` is **not sufficient for untrusted institutional production uploads**.
- Rate-limiting and secrets management do not replace HTTPS, egress controls, alerting, audit retention, data-subject privacy requirements or monitoring.
- Only the public **`/about`** page is intended for search indexing. Dashboard routes and private APIs are marked `noindex`, and authenticated responses are `no-store`.

## Tests and verification

```bash
python -m pytest -q tests/test_e2e.py tests/test_ai_workflow.py
python -m compileall -q app
node --check static/app.js
alembic upgrade head && alembic check
# Optional, requires Playwright and Chromium; frontend mocked-API visual smoke test:
python tests/browser_ui.py
```

The API suite tests permissions, cross-department separation, CSRF, password reset, encrypted integration key, uploaded revisions, immutable rules, document approval/rejection, OCR, malformed model result fallback and Manual Review safety. Browser UI checks use **mock API responses** and do not demonstrate a successful real Render deployment or live model call. To run a production-grade acceptance test, supply real credentials and key to a **staging environment**, test staff document upload, HOD rule version, AI response and Principal/IQAC visibility, and inspect logs.

## Key files

- `app/main.py`: authenticated REST endpoints, audit and authorization
- `app/security.py`: sessions, CSRF, Argon2id hashing and roles
- `app/database.py`: relational schema, connection pooling and indexes
- `app/verification.py`: extraction/OCR, deterministic rules, OpenRouter and result validation
- `app/worker.py`: persistent asynchronous verifier queue
- `app/storage.py`: file magic checks, private download and optional ClamAV
- `app/bootstrap.py`: one-time account provisioning
- `alembic/versions/`: tracked database migrations
- `static/`: original brand assets, responsive interface and public overview
- `render.yaml`: Render Blueprint (Postgres + web + worker)
- `compose.yaml`: standalone server deployment
- `tests/`: API and UI test suites
