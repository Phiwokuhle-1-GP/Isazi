# Isazi V2.6.41 — local owner growth dashboard

Install over V2.6.40 after the cart-only payment-selection patch (Git commit e9ff713). Stop Flask first. This package does not commit, push or deploy.

The owner Overview now opens Traffic, Sales & Growth. All / Test / Real filters apply to saved orders and measured traffic. All is the default during testing; individual orders keep their existing test flags. The orders list also defaults to All. Historical test orders within the chosen 7/30/90-day window are included immediately.

Confirmed order value uses fully paid orders in Paid, Ready or Completed status. It counts each order once, includes delivery, excludes cancellations and is before refunds. Real value and simulated value are displayed separately. Product units and goods values come from those same confirmed orders; goods values are before discounts and delivery. These are not net revenue or profit reports.

Use the existing storefront flow in a signed-out browser: add a product, choose a payment method, register/sign in, confirm delivery and place an order. A simulated gateway success appears in the dashboard; repeating success cannot duplicate a receipt. For PEP, place the test order, open its owner review from the PEP queue, simulate owner payment confirmation using a clearly marked TEST reference, then use the existing dispatch/tracking controls. Test SMS remains labelled Test - not sent and no actual funds are taken. Test and real inventory remain separate. Stock alerts show the current active products below five units in the chosen pool.

Traffic collection starts at installation and does not fabricate history. A signed first-party analytics cookie identifies a browser for up to 180 days; stored events retain a hashed ID, UTC day, public route category, device/browser category and referral category for up to 180 days. No IP, full URL, query string, raw user agent or form content is stored. Owner requests, known bots and Do Not Track requests are excluded. Traffic is tagged test while payment test mode is on. The public privacy page explains this collection. The cookie is analytics, not essential cart functionality; future consent requirements can be configured before public launch.

The shopping journey shows distinct measured browser IDs at each stage independently. It is not a matched cohort conversion funnel: historical orders, untracked traffic and browser changes can make counts differ. No conversion rate is invented. Sources are referral categories, not ad-spend attribution; sources can overlap. Chart daily unique counts cannot be summed to obtain period uniques. The CSV export carries scope, period, real/simulated totals and daily traffic without customer details.

No external GA4, Clarity, payment, courier or SMS integration is added or enabled. Existing payment test mode remains controlled by DEMO_PAYMENTS_ENABLED / START_WINDOWS.ps1. This update includes tests in owner analytics without relabelling them as real. Existing financial reports and commission safeguards remain unchanged.

Install locally:

```powershell
python .\APPLY_OWNER_GROWTH.py --target "PATH_TO_EXISTING_APP" --check
python .\APPLY_OWNER_GROWTH.py --target "PATH_TO_EXISTING_APP"
```

The installer verifies all reviewed code files before writing, backs up changed code, refuses unexpected edits and supports repeat application. It never replaces a database, owner password or uploads. On startup, the app adds growth_events / growth_meta and an index. Existing tables and records are preserved. No reset or test-data deletion is implemented; use the Real filter to isolate real metrics after testing. Plan a backed-up cleanup separately when testing is complete.

Restart START_WINDOWS.ps1. Check /health reports 2.6.41, sign into /owner and refresh with Ctrl+F5. Use a separate signed-out/private browser to generate visits. Automated application and checkout tests use disposable databases; no live transactions or browser visual checks are performed.
