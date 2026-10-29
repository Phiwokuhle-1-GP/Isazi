# Isazi V2.6.4 — Normal store and Render handoff

The normal store and demo share the same templates, CSS, original portraits, product images, testimonial covers, yellow testimonial title, border, nationwide banner, R600 delivery threshold, footer social controls, product navigation, cart, checkout, account pages and owner tools. There is no second older owner website in this source package.

The separate sample database, automatic sample customer and seeded sample stock remain exclusive to standalone demo mode. For the presentation on 29 October 2026, the normal Windows launcher and Render blueprint also enable simulated payments on the main store via DEMO_PAYMENTS_ENABLED=1. A normal purchase requires actual owner-entered stock. Product pages show Add to Cart when stock is positive. New normal-store products begin at zero so unverified inventory is not sold. All six methods can complete a simulated payment on new main-store test orders. These orders carry a permanent payment_test marker and CLIENT DEMO receipt method, appear as Test payment in account/owner screens, and are excluded from real financial reports, verified reviews, notifications and agent commissions. Existing real orders cannot be paid through the simulator. Tests reserve actual normal-store inventory, so cancel test orders afterwards to restore it. No external provider or email server is contacted in payment test mode.

## Local normal-store review

1. Apply the update to the existing installation. Run START_WINDOWS.ps1; it explicitly selects normal mode even if the terminal previously had ISAZI_CLIENT_DEMO=1.
2. Open /health: version 2.6.4, demo_mode false, demo_payments_enabled true for today’s presentation. Sign in through /owner/login using the normal owner password. RESET_OWNER_WINDOWS.ps1 without -ClientDemo resets that owner privately.
3. In the dashboard, edit products and enter verified prices, available stock and product information. Use View storefront to review the same normal store.
4. In Home Images and Media & Testimonials, confirm the portraits, hero, story poster and four covers. Upload the actual recordings here. Normal and demo uploads/settings are separate records. Edits made through the demo backend are not automatically copied into the normal database; upload approved media and enter approved settings in the normal owner backend.
5. In Store settings add the real social profile URLs and contact details. Review delivery text and policies. Current automated rates are collection free, Randburg R50 up to and including R600, free strictly above R600; nationwide orders outside Randburg require a courier quote before checkout. No nationwide rate table or courier booking service is connected.
6. Use a separate browser profile/incognito session for a customer: Shop → product → Add to Cart → cart quantity → checkout → receipt → My Account / My Orders. The main store shows PAYMENT TEST MODE. Complete any of the six simulated payment options and confirm the test receipt appears in My Orders. No automatic sample account is created. Owner sign-in blocks customer sign-in/registration in the same browser until the owner signs out; use a separate browser profile to demonstrate both roles.

## Git source

Commit the extracted inner Isazi_Herbal_Shop_V2 source folder. Do not copy the archive's parent folder into an existing repo with another nested app folder. If this is an existing repository, use its checked-out working folder as APPLY_UPDATE.ps1 -TargetPath, then inspect git status and git diff before committing.

The .gitignore excludes instance/, instance-client-demo/, .venv/, .env, session-key runtime files (within instance), caches and update backups. Never commit SQLite files, customer/order data, uploads containing private content, credentials or merchant secrets. The archive includes source and default public assets, without runtime databases or owner passwords. The source is prepared for the existing Phiwokuhle-1-GP/Isazi repository. See the accompanying handoff message for its pushed commit; a source push does not itself verify a successful Render deployment.

## Render configuration

Use the supplied render.yaml for a Python web service with a persistent disk at /var/data. It uses a paid starter service because the SQLite database and uploaded media need durable disk storage. Check pricing and capacity in your Render account before creating the service.

- Build: pip install -r requirements.txt
- Start: gunicorn --workers 1 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT app:app
- Health check: /health
- ISAZI_CLIENT_DEMO=0
- DATA_DIR=/var/data
- COOKIE_SECURE=1 (HTTPS only)
- SECRET_KEY: use the generated Render secret; retain it across redeployments.
- DEMO_PAYMENTS_ENABLED=1 for the presentation only. Change it to 0 before accepting real orders.
- PAYFAST_ENABLED=0 until real credentials and callbacks have been tested.
- PUBLIC_BASE_URL: set to the actual HTTPS Render/custom domain when configuring provider callbacks and order links.

One worker avoids competing first-start schema/seed migrations; four threads serve concurrent requests using per-request SQLite connections. This is a single-instance SQLite deployment. Do not scale to multiple independent instances/disks without changing the database/storage architecture.

On first deployment, open the Render Shell in that service and run:

```bash
python -m flask --app app create-owner
```

Enter/confirm your private owner password when prompted (16 characters minimum). This creates the owner on the Render disk; the Windows local owner does not transfer automatically. The same command resets it. Keep the prompt password out of Git, chat and shell command arguments.

An empty Render disk starts a new normal store with zero sample stock. Existing local data and uploaded media do not transfer through Git or this package. If keeping local approved content/data, make a consistent database backup while writes are stopped and use a secure data migration process before accepting orders. Do not run init/reset scripts that wipe existing records.

## Deployment acceptance

Verify /health returns 2.6.4 and demo_mode false; sign in to the owner; set confirmed stock; register a customer; place a controlled test order; verify its private receipt, stock reservation and account history; upload/reload an approved media item; restart/redeploy and confirm data/uploads persist. With DEMO_PAYMENTS_ENABLED=0, simulated payment routes must return 404 and test orders must never open a real PayFast payment. Configure and test actual payments separately before advertising live checkout.

This package was checked with temporary Flask databases and local rendered pages. Windows PowerShell, actual Render deployment, persistent-disk restart and external payment/email delivery require verification in their target environments.

## Separate the presentation and live access tomorrow

The temporary setting does not expire automatically. On 30 October 2026 stop the main store and start:

```powershell
powershell -ExecutionPolicy Bypass -File .\START_WINDOWS.ps1 -LivePayments
```

This keeps the normal database/owner but disables simulated completion. It does not configure any merchant connection. On Render set DEMO_PAYMENTS_ENABLED=0 and redeploy/restart. ISAZI_CLIENT_DEMO must remain 0 for the normal store. Use START_DEMO_WINDOWS.ps1 for the separate isolated demo whenever needed. Previously created test orders remain labelled and excluded from real reports after the switch. Cancel them to release stock; do not turn simulated Paid records into real payment confirmations.

## Existing Isazi hosting compatibility

The blueprint retains the existing isazi-herbal-shop-client-portal service name and Frankfurt region. render_start.sh supports the existing bash startup command, maps ISAZI_SECRET_KEY/ISAZI_HTTPS to the new names when needed, selects the normal store and uses /var/data. wsgi.py also exports the new app. The previous PM portal database /var/data/isazi.sqlite3 is not overwritten; this store uses /var/data/shop.sqlite3 and /var/data/uploads. The previous portal owner/account schema is not imported. Create a new shop owner privately via the Render Shell command above. Existing local shop data must be migrated separately if it is needed on Render.
