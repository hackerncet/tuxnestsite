# NCET VerifyFlow — AI-Powered Document Verification and Approval

A database-backed, role-enforced, AI-assisted college document-verification application prepared for **Nagarjuna College of Engineering and Technology (NCET)**. The interface uses the supplied NCET emblem and NGI wordmark. The current deployment hostname and legacy NCET_BOOTSTRAP environment variables remain unchanged to preserve operational compatibility. This is an **independent, deployment-ready implementation**, not a claim of official college endorsement or finished security accreditation.

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
- **HOD** — Creates and manages Staff accounts within their own department (including access and password resets); builds, edits and publishes departmental rulebooks (mandatory headings, phrases, page counts, date, signatures, formatting, writing quality, semantic guidance). Every published version is retained. Reviews documents for their department and approves or rejects with feedback.
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

**Setup and recovery guide:** [Render Deployment Guide](docs/RENDER_DEPLOYMENT.md)


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

## One-command Ubuntu VPS deployment

On a fresh Ubuntu 22.04, 24.04, or 26.04 LTS server, run this single shell command. It downloads the bootstrap script to a temporary file, installs Docker Engine and Compose v2 from Docker's official apt repository when needed, clones the current `main` branch to `/opt/ncet-verifyflow`, then prompts for the public hostname, VPS IPv4 address, initial admin username and password. It generates the database password and Fernet encryption key automatically.

```bash
sudo apt-get update && sudo apt-get install -y curl && tmp="$(mktemp)" && curl -fsSL https://raw.githubusercontent.com/hackerncet/tuxnestsite/main/deploy/ubuntu-one-command.sh -o "$tmp" && sudo bash "$tmp"; result=$?; [ -z "${tmp:-}" ] || rm -f "$tmp"; exit "$result"
```

The installer creates a private `.env` with mode `600`, starts PostgreSQL, the app, its worker, Caddy HTTPS, and a private ClamAV scanner. Uploads fail closed if ClamAV is unavailable. The scanner keeps its signature database in a persistent Docker volume and is not exposed publicly. Allow inbound TCP 80 and 443, plus UDP 443 for HTTP/3, in the VPS provider firewall. ClamAV adds memory and disk use; use a VPS with adequate headroom for the app, OCR, database, and virus signatures.

At the end, the installer prints the actual DNS record to enter at your domain provider: record type `A`, hostname, the VPS IPv4 address, and TTL. It also lists the private server variable names; **do not paste application secrets into DNS fields**. DNS receives only the A record. Caddy can obtain HTTPS after DNS points to the VPS and ports 80/443 are reachable.

After installation, check `cd /opt/ncet-verifyflow && sudo docker compose ps`, `sudo docker compose logs --tail=100 web clamav`, then open `https://<your-hostname>/healthz`. Back up the PostgreSQL and Caddy Docker volumes to encrypted off-server storage. The one-time installer refuses to overwrite an existing `.env`.

### Automatic GitHub-to-VPS updates

The `main` branch workflow can update this checkout after Python, Chromium, SAST, and dependency checks pass. In GitHub repository settings, set the Actions variable `VPS_DEPLOY_ENABLED=true` and add these Actions secrets: `VPS_SSH_PRIVATE_KEY`, `VPS_KNOWN_HOSTS`, `VPS_HOST`, `VPS_USER`, `VPS_DEPLOY_PATH` (normally `/opt/ncet-verifyflow`), and `VPS_PUBLIC_ORIGIN` (for example `https://ncet.paladuguganeshnaidu.tech`). Use a dedicated SSH account with only the access needed to update this deployment; remember that membership in the Docker group grants root-equivalent host access. The workflow pins the SSH host key and runs a public HTTPS smoke check after deployment. Until those values are configured, VPS updates remain skipped.

The one-command installer currently clones `hackerncet/tuxnestsite`, the repository connected to Render. The requested `paladuguganeshnaidu/ncet` repository can replace that source after write access is available and the code is copied there.

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

The public **`/plot`** page reports this browser visit's LCP, INP, CLS, TTFB,
resource sizes, and a one-time `/healthz` response. It does not transmit or store
visitor performance data. Its historical optimization figures are labeled as
local/synthetic source benchmarks; they are not live-user percentiles or Render
latency. A single browser visit cannot certify site-wide Core Web Vitals.

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


## NCET branding transition (October 2026)

The public-facing platform and new document references use **NCET VerifyFlow** and **Nagarjuna College of Engineering and Technology**. The supplied NCET tree/book artwork is preserved as cropped WebP raster assets; no auto-traced or claimed original vector logo has been created. Existing NCET-prefixed document IDs remain unchanged, as do database tables, authentication accounts, secret names, Render service URLs, and audit histories. Confirm organizational publication authority before using the platform for real institutional records.


## BCA Student Services & Projects (2026)

Public pages: `/` and `/students`; authenticated BCA student portal: `/students/portal`; faculty enrollment/HOD case desk: `/bca/manage`; members-only collaboration: `/community`.

- BCA faculty or HOD can import `usn,full_name,semester` CSV (up to 100 students per upload). Passwords are generated once and must be distributed privately. Each student changes the temporary password before participating.
- Students raise confidential requests to the BCA HOD; request details and student records are never indexable or open to unauthenticated users.
- Signed-in users may view profiles with names and USNs, read shared projects and participate in **visible discussion threads only**. There are no direct messages; faculty, HOD, Principal and IQAC may view the board; the BCA HOD and administrator can moderate.
- Two additive Alembic revisions create BCA student, case, and community tables. No existing records or access credentials are reset.
- Before institutional use, rotate exposed credentials, arrange backups, establish abuse/reporting procedures, review USN directory privacy with the institution and use always-on paid worker resources for document processing.


## NCET tasks and DeepSeek verification (feature branch)

At /tasks, a HOD uploads up to 50 reference PDFs per batch, selects unassigned rows and allocates them to same-department staff. The staff inbox has persistent notifications and attached instructions, and PDF submissions enter a durable worker queue. Deterministic checks and DeepSeek reviews provide scored findings and corrections. Scores over 75% without mandatory-rule failure or uncertainty await HOD approval; scores of 75% or below request correction; unavailable or uncertain AI requires manual review. Principal and IQAC can view authorized operational aggregates and work status. Four six-hour Asia/Kolkata windows produce advisory shared-project discussion summaries; private complaints are excluded. Encrypted DeepSeek keys are managed from the administrator task panel or private Render env. Migration: 8d0ncet003. Render Free cannot guarantee scheduled execution when asleep. Production backup and external AI processing authorization are required.
# Ubuntu VPS deployment

For a single-server HTTPS install, install Docker Engine and its Compose v2 plugin using the [official Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/), clone this repository, then run:

```bash
sudo bash deploy/ubuntu-install.sh
```

The installer asks for the public hostname and a new administrator username/password, generates the PostgreSQL password and Fernet settings key, writes a mode-600 `.env`, and starts PostgreSQL, the app, the background worker, and Caddy. Caddy obtains and renews HTTPS certificates after the hostname points to the server and inbound ports 80/443 are reachable. The installer prints the DNS A record details and environment variable names; keep `.env` private. It intentionally leaves document malware scanning disabled (`SCAN_MODE=off`) until a supported scanner service is configured. Back up the PostgreSQL and Caddy volumes before upgrades.

Useful operations: `docker compose ps`, `docker compose logs -f web worker proxy`, `docker compose pull && docker compose up -d --build`, and `docker compose down` (does not delete volumes). The application is available at `/plot` for a browser-local performance snapshot; its measurements are per-browser session, not a server monitoring service.

### Deploy on each GitHub main update

The `deploy-vps` CI job runs only after the Python, Chromium, and SAST/dependency-audit jobs pass on a push to `main`. To enable it, create the GitHub Actions repository variable `VPS_DEPLOY_ENABLED=true`, a `production` environment, and these environment secrets: `VPS_HOST`, `VPS_USER`, `VPS_SSH_PRIVATE_KEY`, `VPS_KNOWN_HOSTS` (pre-verified host key line, not output collected during the workflow), `VPS_DEPLOY_PATH` (absolute path of the cloned application on the server), and `VPS_PUBLIC_ORIGIN` (for example, `https://verify.example.edu`, with no path). Install the matching public key for that user, grant it only the access required to update the application and run Docker Compose, and clone this repository at that path before enabling deployments. Point DNS to the VPS and complete the first manual install before enabling the workflow. After each update it checks `/healthz`, `/plot`, and the student sign-in page over public HTTPS. Protect `main` and require CI checks; configure environment approval if deployments should wait for an operator. Keep the environment disabled until all secrets and the first manual VPS install are verified.
