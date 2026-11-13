AAIS runs one site with Frappe, ERPNext, Education and Builder. Production inputs are resolved to exact commit hashes by `.github/workflows/build-erpnext.yml`. A change to any app is discovered by the scheduled workflow (every 15 minutes, subject to GitHub scheduling delays), or by a manual workflow run. `frappe_docker` uses `production` as its GitHub default branch so the schedule executes the intended workflow.

The release image contains `/home/frappe/frappe-bench/release.json` with every app revision and the infrastructure revision. CI installs all four applications into a fresh MariaDB site, migrates it, checks billing security, checks real student query/document permissions, renders a native full-page Chromium preview, and checks HTTP health before publishing `production` and `latest`. A `release-<source hash>` tag identifies the tested source set. Only this repository publishes the combined image.

The VPS's `aais-update.timer` checks for a tested image every five minutes. Its updater installs the matching Compose/operations bundle from that image, then deploys the immutable registry digest. Deployment preserves the previous container source, enables maintenance, drains workers, creates and verifies an encrypted off-host backup, runs migrations, starts the web services, checks every published school route, and starts workers. It retains a frozen database/files snapshot and previous Compose configuration for failure recovery. A failed migration or route check restores the frozen database and previous image. Do not remove rollback images or snapshots until a later release is verified.

The updater intentionally replaces the role Watchtower previously played for AAIS. School containers have `com.centurylinklabs.watchtower.enable=false`; the host Watchtower also explicitly excludes their names. Unrelated workloads retain their existing update behavior. Compose configuration and operation scripts are shipped in the release image, so they no longer depend on untracked manual copying.

The backup timer runs daily at 02:00 UTC / 08:00 Asia/Dhaka, with up to five minutes of jitter. `/home/nirog/aais-backups/last-success` is updated only after a round trip through the encrypted R2 remote produces the original SHA-256. Thirty days of daily backups are retained. Rclone crypt protects both names and content. Its recovery configuration must be kept separately from the encrypted archive; a protected copy was placed on the operator's local machine during remediation. Rclone credentials and `.env` must never be committed.

Useful host commands:

```bash
cd /home/nirog/aais-erp
./ops/backup.sh
python3 ops/health.py
python3 ops/smoke.py
python3 ops/update.py
systemctl list-timers 'aais-*'
journalctl -u aais-backup.service -u aais-update.service -u aais-health.service
docker compose ps
docker exec aais-erp-backend-1 bench doctor
```

`restore-database.py` is an internal rollback operation and replaces the selected site's database. It must only be used with the frozen release snapshot while all application services are stopped. For a manual disaster restore, first recover the matching Compose file, protected environment file, database/files/config backups, and the exact image; keep maintenance enabled until data counts, roles and page routes have been checked. Restore drills should use a separate database or host.

A fresh installation requires a protected `.env` and these explicit setup steps:

```bash
docker compose up -d db redis-cache redis-queue
docker compose --profile setup run --rm configurator
docker compose --profile setup run --rm create-site
docker compose up -d backend frontend websocket scheduler queue-short queue-long
```

The school website's existing published content remains in the database/sites backup. Versioned Builder template fixtures support the template gallery and fresh installations; migrations skip existing non-template pages so publishing and edits survive upgrades. Source must be changed in Git and rebuilt rather than patched inside an individual running container.

This site is an explicit demo (`demo_site=1`). `education.demo.complete_demo` completes the existing school's fee showcase without deleting academic data or resetting passwords. It uses submitted Sales Invoices as the accounting source; creating submitted legacy Fees for the same period would double-charge the student. `education.demo.verify_access` checks all demo student/guardian identities. Online payment initiation is disabled in the demo; it requires a separately verified gateway and explicit configuration outside demo mode. Real card or bank payments were not used in remediation.

Demo form/content data is illustrative. The public site is marked as a demo, and public pages must not expose private student results. Public content-management features beyond the imported demonstration pages are separate product work.

The host network service blocks direct external ERP and Portainer ports while preserving access through Caddy. SSH uses keys. Dozzle retains authenticated log viewing with shell/actions disabled. Docker JSON logs are bounded in the school Compose services. `aais-health.timer` records container/API/backup health locally and in the journal; no third-party notification destination is configured.
