# NCET VerifyFlow production-readiness audit

## Live state recheck — 21 October 2026, 23:27 IST

This recheck supersedes earlier release-state bullets below where they differ. Earlier entries remain historical evidence.

- GitHub `hackerncet/tuxnestsite` `main` is `2e6281ae668b9074ffc7f9e5a5c4a39bbe70c13e` (PR #82, unknown-account login timing hardening). Render deploy `dep-dbcfo1qjnfac73bt1hqg` is `live`; a fresh `/healthz` response reported the same commit.
- Render confirms the service is connected to `hackerncet/tuxnestsite`, branch `main`, with commit auto-deploy enabled. The service remains free tier with one configured instance. Its live `healthCheckPath` field is empty although `render.yaml` declares `/healthz`.
- A fresh 55-minute Render metrics query (17:00–17:55 UTC, 5-minute resolution) returned web CPU samples of about 0.0040–0.0065 CPU units and memory samples of about 216–276 MB across several instance identifiers during the deploy window. Render still reports one configured instance; the multiple historical identifiers do not establish concurrent scaling.
- The same service metrics query returned no HTTP latency, request-count, or instance-count datapoints. A live p95 latency baseline cannot be inferred from this window.
- The active Postgres instance returned 0–4 active connections, approximately 0.0073–0.0090 CPU units, and about 42–50 MB memory in the same window. It remains a free database expiring 14 November 2026, with external access allowlisted from `0.0.0.0/0`. These reads do not confirm the app's connection hostname or backup recoverability.
- No production settings, DNS, database access rules, or student records were changed. AI external calls remain disabled.

### Remaining production actions

1. Fix the custom-domain TLS failure and verify it in a fresh browser session.
2. Confirm the app uses the same-region internal database URL before restricting external access; establish and test backups, and migrate away from the expiring free database.
3. Apply and verify the Render `/healthz` health-check setting.
4. Provision and verify a fail-closed malware scanner before accepting untrusted institutional documents; the current Render Blueprint has scanning off.
5. Configure VPS Actions secrets and perform a real deployment before claiming GitHub-to-VPS auto-deploy is active.
6. Continue checking the exact deployed SHA after every merge because earlier Render auto-deploy events arrived out of order.
7. Use a disposable student account outside production for student-only publish, request, reply, and inbox workflows.

---


## Passive external security-header scan — 21 October 2026, 23:47 IST

- SecurityHeaders.com scanned `https://ncet-verifyflow.onrender.com` at 18:17 UTC and returned **A+**. The report observed Content-Security-Policy, Permissions-Policy, Referrer-Policy, Strict-Transport-Security, X-Content-Type-Options, and X-Frame-Options. The CSP has `object-src 'none'`, `base-uri 'none'`, `frame-ancestors 'none'`, and `form-action 'self'`; `style-src 'unsafe-inline'` remains in place for current inline styles.
- The response also exposed `server: cloudflare` and `x-render-origin-server: uvicorn`; treat this as minor technology fingerprinting, not proof of an exploitable vulnerability. Removing provider-generated headers would require Render-side controls.
- The same scanner could not complete a TLS handshake to `https://ncet.paladuguganeshnaidu.tech`, consistent with the direct browser failure. It could not assess that hostname's response headers.
- This was an unauthenticated passive HTTP-header scan only. It does not test authenticated workflows, application/API vulnerabilities, dependency behavior at runtime, or exploit resistance, and is not a penetration test.

---

## Live role and student-branch check — 21 October 2026, 23:36 IST

- Against Render commit `53f98ac65e203256f6432fd96917f3b988fb8cd9`, fresh sign-ins succeeded for the supplied `testap` staff, `hod`, and `admin` accounts. Each landed on the expected role dashboard: Staff submissions, HOD department review queue, and the administrator control centre. The HOD navigation exposed the review queue, rules, staff, student requests, and tasks; the admin dashboard exposed user management, AI configuration, and security audit. No account, document, task, complaint, or workflow record was edited.
- After sign-out, the public portfolio for `1NC24CS146` displayed Computer Science & Engineering, semester 5. A read-only query of the same Render database returned the registered department as Computer Science & Engineering and semester 5. The displayed branch and semester match the enrollment row. No other student fields were queried, and no student data was changed.
- The student profile remains voluntarily published; its personal project descriptions and external links are student-submitted and are not independently verified by NCET.
- The custom domain was not used for credential entry because a fresh navigation still failed with `ERR_SSL_VERSION_CIPHER_MISMATCH`.

---

## Latest state check — 21 October 2026, 22:39 IST

This section supersedes the older deployment snapshot below where release state differs. Earlier sections remain historical evidence for the actions performed at their recorded times.

- GitHub `hackerncet/tuxnestsite` `main` and Render's latest live deployment are commit `8da75c69e494532fcc56542dc5e871faa92a6b0a`. Render deploy `dep-dbcf1enlk1mc73fv40ug` succeeded; `/healthz` returned that exact commit.
- PR #78 changed the public student profile into a continuous one-page portfolio. The live `/students/profile/1NC24CS146` page showed all six sections, four projects, 26 skills, student-owned publication controls, Share, and Save as PDF. The profile record was only read; no student data was changed.
- GitHub's full CI and Chromium multi-role audit passed for the merged PR; the security/dependency workflow also passed. The focused portfolio backend suite passed 9 tests, and its browser audit passed at six viewport widths, including keyboard section links, reduced motion, no-JavaScript fallback, sharing, and print.
- Render still reports automatic deploys enabled on `main`, but the service is on the free plan with one instance. Its dashboard `healthCheckPath` remains empty even though the repository Blueprint declares `/healthz`.
- The custom hostname `https://ncet.paladuguganeshnaidu.tech/app` still fails TLS negotiation with `ERR_SSL_VERSION_CIPHER_MISMATCH`. The connected Cloudflare identity call failed with an internal connector error; DNS/certificate changes were not made.
- Render lists the active Postgres instance `test` as free, available until 14 November 2026, with an external IP allow-list of `0.0.0.0/0`. The older `3dulpin-db` is suspended and expired. No database, allow-list, plan, backup, or production record was changed during this check.
- AI external calls remain disabled and no AI service was contacted. The current deployment and security checks do not constitute an independent penetration test, a backup restore drill, or authenticated student publish test.

### Open production actions

1. Repair and verify custom-domain DNS/TLS before using that hostname for account credentials.
2. Verify that Render's `DATABASE_URL` uses the same-region internal connection before restricting external IP access; then confirm backup/restore and migrate from the expiring free database to durable, paid storage with owner-approved spend.
3. Configure fail-closed malware scanning on a reachable scanner before opening document uploads beyond the controlled pilot. Do not set `SCAN_MODE=clamav` until the scanner is actually provisioned and its memory requirements are measured.
4. Set and verify `/healthz` in the Render service settings or synchronize the Blueprint configuration.
5. Rotate the credentials that were shared in the task, without recording the values in this audit.
6. Keep verifying the deployed commit after each main merge because earlier Render webhook events arrived out of order.

## Custom-domain and local security recheck — 21 October 2026, 23:02 IST

- The custom hostname still fails in a fresh browser navigation with `ERR_SSL_VERSION_OR_CIPHER_MISMATCH`.
- Google Public DNS currently returns a CNAME chain from `ncet.paladuguganeshnaidu.tech` to `ncet-verifyflow.onrender.com`, then Render's `gcp-us-west1-1.origin.onrender.com` and its Cloudflare CDN host, resolving to `216.24.57.18` and `216.24.57.16`. No AAAA record was returned. This rules out a stale IPv6 record and points toward a Render custom-domain/certificate association or edge TLS issue; it does not prove which side is misconfigured.
- Render's service details API omits domain and certificate state, and the dashboard session redirects to sign-in. No DNS, certificate, or service-domain settings were changed.
- A fresh local Bandit scan passed (`bandit -q -r app -ll -ii`), with only B104 `nosec` review warnings. A local `pip-audit` request could not reach PyPI because terminal DNS/network access is restricted; the dependency scan remains covered only by the latest successful GitHub security workflow until an online scan can run.
- The current local Windows run collected 158 tests but did not complete before the test process was stopped; it is not a pass or fail result. GitHub CI for the portfolio release had already passed. No student or production records were changed and no AI services were called.

**Observed:** 21 October 2026, 21:46 Asia/Kolkata  
**Live service:** ncet-verifyflow on Render  
**Source:** hackerncet/tuxnestsite main, deployed commit bad4683e57c87ad1497e10a43c8ce6d7fb231e66  
**Scope:** public profile and performance pages; supplied admin, HOD, and staff sign-ins; task and complaint panels; notifications; one authorized synthetic task submission; Render service, database, deployment, and metric evidence; GitHub CI/security checks; student portfolio UI follow-up.

This is a focused release audit, not a penetration test or institutional approval. The production AI gate remained disabled. The synthetic task submission described below was the only production data change made during this run.

## Verified release state

- Render reports the service connected to https://github.com/hackerncet/tuxnestsite, branch main, with automatic deploys on commit. It runs one instance on the free plan.
- Admin, HOD, and staff sign-ins succeeded on the Render hostname. Role-specific dashboards loaded. No account, password, rule, complaint, or HOD decision was changed.
- The HOD complaints dashboard loaded and showed zero cases. The HOD task dashboard loaded three records; the staff view showed one assigned test task and its inbox.
- The user-provided student profile at /students/profile/1NC24CS146 loads as a student-owned portfolio with projects first, share and PDF actions, and an edit/publish path.
- Follow-up release PR #69 improved the project gallery and made the student edit/publish action explicit. After the live deploy, the profile rendered with four project cards and its action opened the student portal sign-in route. The editor source confirms students can publish/unpublish and save portfolio updates; an authenticated student save was not exercised because no student credentials were supplied. No student data was changed.
- The live /plot page reported one browser sample: LCP 944 ms, CLS 0.000, TTFB 256 ms, 5.3 KB transferred, and a successful /healthz response in 373 ms. INP was not measured because no qualifying interaction occurred. These are one-visit measurements, not field percentiles.
- Render metrics for the queried 24-hour period returned memory samples, with the latest around 260 MB. CPU, HTTP request-count, and latency series returned no usable samples; no live p95 latency conclusion can be drawn.
- GitHub Actions for PR #66 head 39c0091cce715199dfd37d96525f2af4b75c6ceb completed successfully: NCET VerifyFlow CI run 983 and NCET Security Audit run 399.
- The notification inbox showed a new staff task notice and HOD submission/verification notices. Render request logs show /api/alerts/inbox requests at approximately 1.5-second intervals, matching the intended refresh cadence.

## Authorized production workflow simulation

Using the existing synthetic task ncet-workflow-test.pdf (task 3) and the existing staff account, the task's reference PDF was downloaded from the app and submitted through the staff upload control. Render logged POST /api/tasks/3/submit as 201 Created. Deterministic processing completed and moved the task to manual review; the UI clearly said the HOD should review the findings manually and that no AI decision was assumed. The HOD inbox received both submission-started and verification-completed notices.

The submitted file and task record remain in production in manual review. No task was deleted, no student was created or deleted, no inbox item was marked read, and no HOD approval/rejection was issued. AI-provider calls were not tested or requested.

## Findings and actions

| Priority | Finding | Evidence and recommended action |
|---|---|---|
| High | The custom hostname does not complete TLS negotiation. | Browser navigation to https://ncet.paladuguganeshnaidu.tech/app returns ERR_SSL_VERSION_CIPHER_MISMATCH before the app loads. Earlier DNS checks showed the hostname resolving to Render, but the current Render dashboard session redirects to sign-in and the connector does not expose domain-certificate controls. Fix/verify the domain and certificate in the authenticated Render dashboard before using that hostname for logins. |
| High | Passwords were shared in the task and used for the three successful Render sign-ins. | The values are intentionally omitted. Rotate them through the supported account-management flow and store replacements in the operator's password manager. |
| High | Render Blueprint configuration sets SCAN_MODE=off and defines no scanner service. | This is a repository configuration finding; the effective secret environment was not read. Before accepting untrusted institutional documents, configure a reachable malware scanner with fail-closed behavior or keep uploads restricted to controlled pilot use. |
| High | The active database is a free instance named test and expires 14 November 2026. | The live task submission updated task 3 to manual_review in that database at 2026-10-21 14:55:17Z, confirming it serves the running app. The older 3dulpin-db is suspended for billing after its 9 October expiry. Both instances list inbound access as 0.0.0.0/0. Take and verify a backup, restrict access to required sources, and migrate to durable managed storage before expiry. |
| High | Render compute is free tier with one instance. | Free capacity can sleep and does not guarantee always-on verification work. Move to always-on compute and a separately monitored worker before promising institutional deadlines. |
| Medium | Render service health-check configuration is out of sync with the repository Blueprint. | render.yaml declares healthCheckPath: /healthz, and the endpoint returns healthy, but the live service settings still report an empty path. Sync the Blueprint or set the live service field, then re-read the service configuration to confirm. |
| Medium | Render HTTP latency and request metrics are unavailable in the queried series. | Add operational telemetry and alerting for request latency, worker queue age/failures, and database/storage health. The /plot page is intentionally a local browser sample and is not site-wide telemetry. |
| High | Render's commit webhook repeatedly deployed older main revisions after newer releases. | After PR #69 merged 2d460e3, a delayed new_commit event for a65eb62 started and became live, so 2d460e3 had to be redeployed manually. After PR #70 advanced main to e069f73, another delayed new_commit event for 2d460e3 became live; a manual deployment then restored e069f73. /healthz confirmed e069f73. Investigate Render's GitHub webhook/event queue and verify the deployed SHA after every merge until the branch-head deployment is reliable. |
| Medium | VPS auto-deployment is not proven active. | The repository includes a one-command Ubuntu installer and a main-to-VPS workflow, but deployment is gated by VPS_DEPLOY_ENABLED and private SSH/host/origin secrets. No VPS host was available to verify a real deployment. Configure the values privately and verify a controlled deployment before relying on automatic updates. |
| Medium | Student-authenticated production workflows remain unverified. | The supplied test accounts are admin, HOD, and staff. Student account creation, private requests/replies, contribution requests, and student notifications still need an authorized non-production or disposable student account. |
| Medium | Backup recovery and retention have not been demonstrated. | Confirm backup schedule, retention, restore procedure, upload retention, and encryption. Run a restore drill before handling sensitive academic records. |
| Low | Full external penetration and load testing have not been performed. | Passing application tests, Chromium checks, Bandit, and dependency scans is useful release evidence but does not prove resistance to real-world attacks or capacity under representative load. Arrange an authorized independent review before institution-wide use. |

## Release gate

The Render hostname is usable for continued controlled pilot checks, but the evidence does not support a claim of 100% correctness or unrestricted production readiness. Resolve custom-domain TLS, rotate task-shared passwords, enable fail-closed malware scanning, and establish durable database backups and always-on processing before accepting sensitive records at scale. Keep AI disabled until the institution explicitly configures and approves a provider.


## Student portfolio release and deployment recheck — 21 October 2026, 20:48 IST

- PR #69 merged into main as commit 2d460e3af53f5df1957fbac9e3525da4a6d1fdb7. It creates responsive project cards, labels the owner action “Student: edit & publish”, and clarifies public/private profile behavior while retaining the NCET navy/orange theme.
- Render deployment dep-dbcdeluq1p3s73d320kg completed successfully. The live /healthz response reported commit 2d460e3af53f5df1957fbac9e3525da4a6d1fdb7, and the live profile displayed the updated action and project section.
- The edit link opened /students/portal#portfolio and showed the student sign-in page. No student credentials were provided, so no authenticated portfolio save/publish was submitted. No student record was changed.
- Render then delivered a delayed new_commit deployment for a65eb62ecb2849223977698201641a8d7bebd8c3, which temporarily replaced the newer release. A second manual deployment restored 2d460e3. This is direct evidence that Render auto-deploy is currently unreliable even though the service reports autoDeploy=yes and autoDeployTrigger=commit.
- The service's current repository blueprint declares healthCheckPath: /healthz, but Render's live service settings still show an empty path. The Blueprint-to-service sync has not been verified.


## Repeated Render commit-order check — 21 October 2026, 21:04 IST

- PR #70 advanced GitHub main to e069f73d1879be29239b9a1ea507729e7f8023a1 at 15:27:27Z. Render later processed a delayed new_commit event for the previous 2d460e3 commit and made it live at 15:29:54Z.
- A manual deployment of the actual main head e069f73 started at 15:31:49Z and became live at 15:33:28Z. A fresh browser request to /healthz returned {\"ok\":true,\"commit\":\"e069f73d1879be29239b9a1ea507729e7f8023a1\"}.
- The pattern confirms automatic deploy delivery is out of order across successive main commits. Keep the post-merge exact-SHA smoke gate and investigate the Render event queue; do not rely on the service's autoDeploy=yes flag as proof that the latest main commit is live.


## Render state refresh — 21 October 2026, 21:16 IST

- GitHub main and the latest completed Render deployment both report commit 9b51ad0510cb03270d9b01bdf1355947417a19d8. Render lists that deployment as live, triggered by API, and completed at 15:42:34Z. The exact-SHA live health check was confirmed after the deploy.
- Render still reports automatic deploys enabled for commits on main, a free plan, and one configured instance. The earlier out-of-order webhook finding remains relevant; this refresh confirms the current head is live at this observation time only.
- In the queried 75-minute metrics window, CPU and memory returned samples. Memory ranged from about 103 MB to a peak of about 258 MiB; the latest sample was about 230 MiB. HTTP latency and request-count series remained empty, so these data do not establish an application-wide latency baseline.
- The service configuration still reports an empty healthCheckPath despite render.yaml declaring /healthz. The Blueprint/service configuration mismatch remains open.


## Staff workflow and cache verification — 21 October 2026, 21:46 IST

- Main is `bad4683e57c87ad1497e10a43c8ce6d7fb231e66`. Render deployment `dep-dbce9ll9fdbs73cojku0` completed successfully, and the live `/healthz` endpoint reported that exact commit.
- PR #73 clarified the staff upload notice: AI checks run only if the institution configures and enables an approved provider; otherwise the submission requires HOD manual review and no AI result is assumed. No provider was contacted.
- The first live check after PR #73 still showed the old notice because the HTML retained the old `app.js` URL. PR #74 incremented the script asset version. A fresh live staff session then loaded `/static/app.js?v=20261021-ai-policy-gate-2` and displayed the revised notice.
- The supplied `testap` credentials authenticated successfully as a STAFF account in Computer Science & Engineering. Read-only checks covered overview, document list, status filter and search, submission form, activity timeline, account information, and help. The submission form was inspected but not submitted; no documents, passwords, or workflow records were changed.
- The account is staff, not a student. Attempting it on the student portal returned the expected invalid username/password/role response; student-only publish, request, and reply workflows remain unverified without a student account.
- PR #73 and PR #74 CI and security checks passed. The main-push Render smoke job passed after the current SHA was manually deployed. Repeated delayed auto-deploys continued to promote prior commits before the exact main SHA was restored.

