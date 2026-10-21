# NCET VerifyFlow production-readiness audit

**Observed:** 21 October 2026, Asia/Kolkata  
**Live service:** `ncet-verifyflow` on Render  
**Source:** `hackerncet/tuxnestsite` `main`, commit `ed53a2a4e7970fbaccef799d3f633c22317eb947`  
**Scope:** public pages, read-only role sign-ins, notification inbox, deployment configuration, Render service metrics, and GitHub CI/security workflows.

This is a focused release audit, not a penetration test or institutional approval. No production records were created or changed, no notification was marked read, and no AI provider was called.

## Verified release state

- Render reports the service as live on `main`, sourced from `hackerncet/tuxnestsite`, with automatic deploys enabled. The service uses the free plan and one instance.
- GitHub Actions run 799 (NCET VerifyFlow CI) and run 214 (NCET Security Audit) for the deployed commit completed successfully. CI includes the Python suite, Chromium role and responsive UI workflows, installer/Compose validation, Bandit, and `pip-audit`.
- Read-only sign-in succeeded for the supplied administrator, HOD, and staff roles on the Render hostname. The role-specific dashboards rendered; HOD and staff notification inboxes loaded. The staff inbox displayed an existing unread task notice. No document, task, user, or read-state records were changed.
- `/notifications` requires authentication. For the authenticated HOD and staff sessions it rendered the inbox and the “updates automatically every 1.5 seconds” status. The live notification panel showed existing role activity.
- Public home and About pages rendered the NCET lockup and NAAC A+ identity. The published lockup is a 2000 × 964 PNG.
- The HOD's department complaint, enrollment, and project pages returned their department-scoped views during the read-only session. No updates were submitted.
- The live `/plot` page reported one browser sample: LCP 736 ms, CLS 0.000, TTFB 268 ms, 5.3 KB transferred, and a successful `/healthz` response in 344 ms. INP had no value because no qualifying interaction occurred. These are one-visit measurements, not field percentiles.
- Render metrics returned memory samples up to 269,766,660 bytes (about 257 MiB). Its HTTP request-count and latency queries returned no samples, so no live p95 latency conclusion can be drawn.

## Findings and actions

| Priority | Finding | Evidence and recommended action |
|---|---|---|
| High | The requested custom hostname does not complete TLS negotiation. | Browser navigation to `https://ncet.paladuguganeshnaidu.tech/app` returned `ERR_SSL_VERSION_OR_CIPHER_MISMATCH` before the app loaded. Do not enter credentials on that hostname until its DNS target and certificate are corrected and verified. The Render hostname remains reachable. |
| High | Account passwords were shared in the task. | Admin, HOD, and staff sign-ins worked on Render. Rotate the shared passwords through the supported account-management flow, then store replacements only in the operator’s password manager. Password values are intentionally omitted here. |
| High | Render’s checked-in Blueprint sets `SCAN_MODE=off` and declares no scanner service. | The active Render environment was not read because it can contain secrets, so this finding describes repository configuration rather than an asserted live override. Verify the effective setting privately. Before accepting untrusted documents, provision a reachable scanner and enable fail-closed scanning; otherwise pause uploads or keep the service in controlled pilot use. The Ubuntu Compose deployment includes private ClamAV. |
| High | Render runs on the free plan with one instance. | Free capacity can sleep and is not a reliable always-on worker for institutional deadlines. Move to always-on compute and a separately monitored worker before promising continuous processing. |
| High | The active Render database and its continuity are unconfirmed. | Render lists one free Postgres instance as suspended after its 30-day expiry on 9 October 2026 and another free instance as available until 14 November 2026. Both list inbound access as `0.0.0.0/0`. The service's active `DATABASE_URL` was not read, so the attached instance cannot be identified from this audit. Privately confirm which database the live service uses, take and verify a backup, restrict inbound access to required sources, and migrate to durable storage before expiry. |
| Medium | Render has no configured service health-check path. | The service settings report an empty `healthCheckPath`, although `/healthz` returned healthy in the browser sample. Set `/healthz` in the service configuration so deploy readiness and health replacement use the application's health endpoint. |
| Medium | HTTP latency and request metrics are unavailable in the queried Render series. | Add or enable operational telemetry and alerting for request latency, worker queue age/failures, and database/storage health. The `/plot` page is intentionally a local browser sample and is not a substitute. |
| Medium | The custom-domain certificate and end-to-end DNS route remain unverified. | No certificate bypass was attempted. After fixing the domain at the DNS/Render controls, validate the certificate chain and health route before inviting users to sign in. |
| Medium | VPS automatic deployment is not yet proven active. | The repository contains a one-command Ubuntu installer and a `main`-to-VPS Actions job, but that job is gated by `VPS_DEPLOY_ENABLED` and private SSH/host/origin secrets. No VPS host or secrets were provided to this audit, and the installer was not run on a real Ubuntu VPS. Configure these privately and verify a controlled deployment before relying on auto-updates. |
| Medium | Student-authenticated production journeys were not exercised. | No student login was included in the supplied test accounts. Local API/browser tests cover the student portal; production account creation, requests, replies, project contributions, and student notifications still need a non-production or explicitly approved disposable student account. |
| Medium | Production restore and retention were not demonstrated. | Confirm the database’s backup schedule, retention, restore procedure, upload retention, and encryption outside this code-only audit. Run a restore drill before using sensitive academic records. |
| Low | A full external penetration/load test has not been performed. | Passing Bandit, dependency scanning, automated application tests, and browser checks is valuable release evidence, but it does not establish resistance to real-world attacks or capacity under representative load. Schedule an authorized independent review before institution-wide production use. |

## Release gate

The Render release is healthy enough for continued controlled pilot use, but the evidence does **not** support a claim of 100% correctness or unrestricted production readiness. Fix the custom-domain TLS issue, rotate the task-shared credentials, privately confirm malware-scanning configuration, and establish backups/always-on processing before accepting sensitive records at scale. Keep AI disabled until the institution explicitly configures and approves a provider.

