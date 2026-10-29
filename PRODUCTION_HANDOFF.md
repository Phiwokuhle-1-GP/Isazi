# V2.6.6 Git/Render handoff

The unified store, customer journey, test-stock behaviour and owner dry-run operation are documented in README.md and CLIENT_DEMO_GUIDE.md. This source includes all latest visuals/media controls. Customer accounts are required to buy; owners cannot purchase.

## Render

Existing repository: Phiwokuhle-1-GP/Isazi, branch main. The blueprint retains isazi-herbal-shop-client-portal and Frankfurt, uses a paid service with persistent /var/data disk, builds requirements.txt and starts bash render_start.sh. Keep the existing disk attached.

The wrapper starts one Gunicorn worker with four threads and maps legacy ISAZI_SECRET_KEY/ISAZI_HTTPS when new names are not present. SECRET_KEY must remain stable. DATA_DIR defaults to /var/data. ISAZI_CLIENT_DEMO is forced to 0. DEMO_PAYMENTS_ENABLED defaults to 1 for the dry run. Set it to 0 to disable simulation after presenting. COOKIE_SECURE must be 1 on public HTTPS.

The new store database /var/data/shop.sqlite3 and /var/data/uploads persist on disk. The former PM portal /var/data/isazi.sqlite3 is not overwritten or imported. Local Windows databases/uploads do not travel through Git. Existing normal-store V2.6.4 databases migrate additively with presentation_stock and stock_pool; orders, accounts, payments and actual stock are preserved. Each new test product starts with 50 presentation units; restart does not replenish consumed stock.

On first deployment create/reset the unified shop owner privately in Render Shell:

```bash
python -m flask --app app create-owner
```

Enter and confirm a password of at least 16 characters. No owner password or runtime database is shipped/committed.

## Accept the deployment

Verify /health version 2.6.6, demo_mode false and demo_payments_enabled true. Sign into owner management. In a separate browser profile register a customer; open a product with test stock; add/update cart; check out; simulate payment; verify receipt/My Orders. In the owner profile verify that saved test order, update its status and inspect Reports → Test orders / dry run. Restart/redeploy and confirm orders/uploads remain. Cancel a test order and verify presentation stock restores once.

No real payment/email is sent in payment test mode. Test orders are permanently labelled and excluded from real report totals, commissions, notifications and verified-purchase reviews. An existing real order cannot be marked paid through the simulator. Test orders cannot be sent to a live provider.

After the dry run set DEMO_PAYMENTS_ENABLED=0 and restart. Real stock is then enforced; configure/verify merchant credentials, public HTTPS callbacks and email separately. The switch does not enable a merchant account. Test order history stays visible. Test and real reporting remain separate scopes in the same owner backend.

## Source publication

PUSH_GITHUB_WINDOWS.ps1 uses Downloads/Isazi_Git_266, validates RELEASE_FILES.json, pushes a backup branch and replaces source with a normal commit. Use the extracted package as source; apply the updater to the installed Downloads app separately. The .gitignore excludes runtime data, environment secrets, caches, ZIPs and update backups. Render may auto-deploy after push if enabled; verify its logs independently.

PowerShell and Render connectivity must be tested on their target systems. All backend verification here uses isolated temporary data; browser QA uses rendered Flask HTML.

V2.6.6 adds responsive image assets, negotiated text compression, private HTML/public static cache handling and the phone layout. optimize_assets.py is invoked during build/start; keep it and asset_manifest.json with the source. PERFORMANCE_NOTES.md records the checks. No database migration/reset is required for this performance update.
