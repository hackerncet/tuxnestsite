# NCET VerifyFlow — Department Task Operations

The official institutional display name is **Nagarjuna College of Engineering and Technology (NCET)**. The existing Render hostname and database secret variable names are kept for compatibility. Historic NCMS-prefixed document/case identifiers are never renamed or altered.

## Roles and primary workflow

- **HOD:** Upload 1–50 PDF reference tasks (maximum 10 MB per file and 60 MB per batch), tick selected unassigned files, select active same-department staff, enter notes and a rule checklist, assign tasks. May hold/release unsubmitted tasks, inspect AI reports and approve or ask for corrections. Every action is audited.
- **Staff:** Open `/tasks` for assigned references, app-only notifications and instructions. Upload a completed PDF, watch status through refresh/polling, inspect pass/issues, and submit a correction if requested.
- **Principal / IQAC:** Read institutional task statuses, approval counts, current workload and aggregate approved quality metrics. Cannot make HOD assignments or change approval decisions.
- **Administrator:** Manage DeepSeek integration under `/tasks` using an encrypted API key and oversee metrics. Existing role and password workflows are retained.

## AI and scoring

1. Existing `/api/documents` uploads retain the versioned HOD rulebook and background worker; new submissions prefer DeepSeek (direct API if `DEEPSEEK_API_KEY` or an encrypted `deepseek_key` is configured, otherwise DeepSeek V3.2 routed via the existing OpenRouter key).
2. Task submissions run deterministic checks first, then a structured DeepSeek rule review. Findings are validated server-side. AI text is never executable code.
3. Each validated rule carries equal weight. A mandatory requirement failure returns for correction regardless of aggregate score. Fully assessed score **above 75%** advances to HOD. Score **75% or lower** is returned for corrections. Low-confidence, incomplete, unreadable or unavailable AI goes to **manual review**, *not* automatic acceptance or rejection.
4. Final institutional approval requires an explicit HOD action and an audit entry. The staff report is advisory, with evidence and correction suggestions, not an objective measure of personal merit.

DeepSeek official API endpoint: `https://api.deepseek.com/chat/completions`; OpenRouter fallback: `https://openrouter.ai/api/v1/chat/completions`. Do not embed keys in any frontend or repository file. External AI processing requires institutional authorization for document content. Usage and charges are determined by the active provider/model and account quota.

## Student collaboration summaries

The BCA project community remains behind login. Student names and USNs can be seen only by authenticated institutional users. Public student-services pages contain neither student profiles nor complaints. Shared discussion posts/comments are summarized in **four six-hour slots per day in Asia/Kolkata**. Only the BCA HOD can view neutral discussion topic digests. No private student-HOD complaint text, names, USNs or email addresses are intentionally transmitted for these summaries. AI flags require HOD review; no automatic member discipline, emotional profiling, or opaque rank scores are created.

**Important:** The current Render Free plan sleeps when idle. Its background worker cannot guarantee four on-time summaries per day, timely task verification, or uptime. For actual institution-wide production, provision an always-on worker/cron, monitored queue, malware scanner, backups, document retention controls and an approved AI-data policy. This repository does not silently incur paid-plan charges.

## Database deployment

Migration `8d0ncet003` adds `task_batches`, `task_items`, `task_submissions`, `task_notifications`, `discussion_digests`. Nothing is dropped or overwritten. Take a PostgreSQL snapshot/backup before applying production migrations. Downgrade is intentionally disabled to avoid accidental document loss. A safe code rollback leaves the unused additive tables in place.

## Verification and operations

- CI: all `tests/test_*.py`, `alembic upgrade head`, `alembic check`, `node --check` on frontend scripts, Chromium browser role/mobile smoke tests.
- Production: confirm healthy `/healthz`, admin login, HOD assignment, notifications, staff upload, AI provider connectivity (test-only PDF), HOD decision, oversight counters; check scheduled summaries when the worker is awake.
- A provider **configured** state is not proof that a live AI call succeeded. Confirm actual report `ai_used=true`, valid results, and review warnings before claiming AI completion.
- Keep secrets in Render variables or encrypted admin settings and rotate previously disclosed passwords.
