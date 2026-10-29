# Isazi V2.5 — Connected store setup

## Working routes

| Experience | Entry point | Included behaviour |
|---|---|---|
| Catalogue | `/shop` | All active products, category counts, search and sorting |
| Product | `/product/1` | Gallery, quantity, information tabs, saved items and moderated purchase reviews |
| Cart / checkout | `/cart`, `/checkout` | Quantity updates, promotions, shipping, stock reservation and agent attribution |
| Customer | `/account` | Registration/login, own orders, details, addresses, password change and saved products |
| Guest tracking | `/track` | Order reference, checkout email and last four phone digits required |
| Contact | `/contact` | Enquiry form stored in the owner dashboard, business hours and location link |
| Owner operations | `/owner/integrations` | Six connected modules, configuration readiness and audit history |
| Sales agents | `/agent/login` | Owner-approved accounts, referral link and own commission ledger |

The white navigation, long homepage and testimonial management remain. The public catalogue contains the six existing sample products on a fresh installation. Adding an active product in Owner makes it available in Shop automatically. Reference-image product counts and stars are not invented: only published verified reviews contribute ratings. Confirm real product information, prices and stock before trading. Demo artwork is described in DEMO_ASSETS.md.

## Updating and data

Use APPLY_UPDATE.ps1 as described in README.md. Stop the server first and make a consistent private backup of the complete `instance/` folder. The updater backs up replaced code but does not back up runtime data. It preserves the existing database, uploads, session key, owner account and virtual environment. New tables are created additively on startup. No demo customer, agent, password or test order is shipped.

On first V2.5 startup, a one-time finance migration records legacy orders already labelled Paid, Ready or Completed as received payments. It does not contact a provider or charge money. Review old statuses before updating and reconcile those records against your actual receipts. Subsequent startups do not repeat the migration.

The database, uploaded media and session key must persist together. Use one service instance with a persistent disk for this SQLite build. Public hosting is not included or deployed by this package.

## Customer and agent access

Customers register through the account icon. Passwords require at least 16 characters and are hashed. Each order belongs to the account signed in when it was placed. Existing guest orders are not exposed merely because an account uses the same email address. A customer can claim a guest order from its private receipt if its checkout email matches their account and it is not already claimed. Receipt URLs contain private access tokens: share them only with the customer.

Saved addresses and items are restricted to their account. Password change requires the current password and invalidates other existing account sessions. Automated email verification and forgotten-password recovery are not implemented in this release; account email is read-only. Do not promise these flows during the demo.

Owner → Agents creates an approved agent and a private activation link. The link lasts 24 hours and works once; the owner shares it separately. No invitation is automatically sent. Agents activate their own password, then use `/agent/login`. Pausing an agent blocks new attribution/access. Agents see their own attributed orders and ledger without customer contact details or receipt tokens.

A referral link `/r/CODE` attributes new orders for up to 30 days; checkout also accepts an approved code. The commission rate is saved when the order is created. Later rate edits affect future orders. Commission accrues after a payment is recorded and the order has a paid/ready/completed status. It excludes delivery and discounts; merchandise refunds adjust the amount and cancellations reverse it. Refunds after a payout can leave an adjustment owed by the agent. There is no automatic clawback or bank transfer.

Owner → Commissions records payouts already completed externally. Enter the actual external reference. It prevents paying beyond the available recorded balance and duplicate references for that agent.

## Orders, promotions and refunds

Money is stored as integer ZAR cents. Prices, discounts, agent codes and stock are checked again on the server inside checkout's reservation transaction. Percent/fixed promotion codes have optional minimum subtotal, expiry (UTC), active flag and usage cap. Non-cancelled order reservations count toward the cap; cancellation releases the use.

Delivery is free for collection. Randburg delivery is free when merchandise after discounts exceeds R600; otherwise it is R50. Other locations require enquiry. Cancellation restores stock once and cannot be reopened. Stale reservations do not expire automatically: cancel them manually after checking payment status.

When using manual payment, verify the actual receipt outside the app, then explicitly mark the order Paid. Ready or Completed alone does not establish a new payment. The system keeps payment receipts separate from order status. A browser payment return is never proof of payment.

Owner order pages record refunds already completed outside the app. Enter separate merchandise, shipping and overpayment amounts plus a reason and external reference. Recorded refunds cannot exceed the relevant receipt balances. The record changes reports and commission balances; it does not send money or restock a physical return. Reconcile physical returned stock separately. Payout and refund records are append-only; double-check references before submitting.

Reports filter by order creation dates and distinguish receipts, refunds and net receipts. They are operational reports, not tax invoices or a full accounting ledger. Customer records group order contacts for owner follow-up; they do not grant customer-account access to legacy orders.

## Optional PayFast hosted payment

PayFast was selected as the implemented hosted-provider option. It is disabled by default. The app never collects card details. Configure these environment variables using your own merchant account and a public HTTPS deployment:

```
PUBLIC_BASE_URL=https://your-real-store-domain.example
PAYFAST_ENABLED=1
PAYFAST_MODE=sandbox
PAYFAST_MERCHANT_ID=your-sandbox-merchant-id
PAYFAST_MERCHANT_KEY=your-sandbox-merchant-key
PAYFAST_PASSPHRASE=your-configured-passphrase
COOKIE_SECURE=1
```

The `.example` domain above is illustrative: replace it with your actual store domain. Environment variables must be set in the process/hosting environment; `.env.example` is not loaded automatically. Never put secrets into screenshots, Git, uploaded assets or Store Settings.

The private receipt offers hosted payment only when all required configuration is present. The customer chooses to continue to PayFast. The ITN callback is `/payments/payfast/itn`. Callback verification checks the signature, merchant, provider source IP, exact amount and PayFast's server response. Only a verified COMPLETE notification records payment. Duplicate notifications are idempotent. A payment arriving after cancellation is retained for owner review and does not reopen the order or reserve stock again.

`PAYFAST_ALLOWED_IPS` can override the built-in provider CIDR list only if PayFast officially changes it. Defaults are in payment_gateway.py. If the host places a reverse proxy in front of Flask, set `TRUSTED_PROXY_CIDRS` to only the actual trusted proxy CIDRs supplied by the host. With it unset, the direct connection IP is checked. Never trust `0.0.0.0/0`, `::/0` or arbitrary forwarded headers. Confirm the host's forwarding behaviour before relying on ITN delivery.

Official integration reference: https://developers.payfast.co.za/docs/itn-instant-transaction-notification/

No merchant sandbox or live transaction was performed here. Before using live mode, complete a real merchant sandbox test from checkout through the public callback, verify the matching receipt and replay behaviour, and test cancellation/late payment. Then configure the correct live merchant credentials and `PAYFAST_MODE=live`. Code readiness does not establish provider approval or successful public connectivity. Online provider refunds are not implemented; issue them in the provider dashboard and record the result in Owner.

## Email, WhatsApp and delivery

Order events prepare notification drafts in Owner → Notifications. They do not send automatically. For email, configure PUBLIC_BASE_URL plus:

```
SMTP_HOST=your-smtp-host
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_FROM=orders@your-real-domain.example
SMTP_USER=your-smtp-user
SMTP_PASSWORD=your-smtp-password
```

Use a single bare sender address in SMTP_FROM. Use `SMTP_SECURITY=ssl` with the provider's SSL port (usually 465) if required. TLS certificate checks remain enabled. Credentials may be omitted for an explicitly authorised SMTP relay. Set up your sender domain with the mail provider, then send a controlled test through the owner screen. No email was sent during development.

An owner previews a draft and clicks Send Email explicitly. Sent/Sending records cannot be sent twice through the normal action. If a send fails, check the mail provider before retrying: delivery can be ambiguous after a network failure. A process crash can leave a row Sending; reconcile with the provider before any administrator repairs that state in the database. There is no background queue/retry worker.

WhatsApp opens a prefilled draft for the owner to review and send. It is not a WhatsApp Business API integration. No message is sent merely by opening it.

Owner order delivery controls store the status, courier name, tracking reference and optional HTTPS tracking URL. Customers see these on the private receipt/account order. Booking labels, courier API calls and automatic courier tracking are not connected. Contact's location link opens a map search for the configured business location; no verified street pin is claimed.

## Demo and verification

1. Start the updated app and confirm `/health` reports 2.5.
2. Click Shop in the header: it opens the full `/shop` catalogue. Show search/category/sorting.
3. Open a product and demonstrate quantity controls and the information tabs. Replace approved product information/gallery through Owner → Edit product.
4. Confirm actual stock before checkout. Show promo codes, a customer account and the private order receipt. Cancel demo reservations afterwards.
5. In Owner → Operations, demonstrate products/customers/reports, agents/commissions, gateway readiness and notification drafts.
6. Keep payment and email disabled for an offline demo unless you have configured and separately tested the services.

70 automated checks passed using isolated temporary databases, including access boundaries, stock/discount transactions, payment callback verification/replays, late payments, refunds, commissions, draft email delivery with mocked SMTP, verified review moderation and gallery editing. No real payment or outbound message was sent. Six viewport widths (1911, 1366, 1024, 768, 390, 320) were checked for Shop, Product, Cart, Account, Contact and Operations without document overflow after layout fixes. Browser checks used exported Flask-rendered HTML; backend flows used Flask's test client. Windows PowerShell and public hosting/provider connectivity were not executed in this environment.

V2.6 demo-specific browser checks covered Product, Cart, Checkout, payment selection, payment preview, receipt and My Account at the same six widths without document overflow. All provider actions remain simulated in client-demo mode.

V2.6.4 main-store presentation: DEMO_PAYMENTS_ENABLED=1 enables six simulated methods without selecting the separate sample database. Orders created in this mode are permanently flagged, excluded from real report totals and commissions, and blocked from real PayFast checkout. Owner/customer sessions are exclusive. The Render blueprint enables this temporary mode; change it to 0 after the presentation. See PRODUCTION_HANDOFF.md.

V2.6.5 supersedes the separate-demo launcher workflow: use START_WINDOWS.ps1 for one site/database. It provides persistent presentation stock, mandatory customer accounts, owner purchase blocking, saved test orders/receipts, and Reports scopes for real/test orders. See README.md for the current operating instructions. Existing real stock and earlier order stock pools are preserved.

V2.6.6 performance/mobile update passes 74 checks; source-image variants, cache headers and text compression preserve registered checkout, owner restrictions, saved dry-run orders, reports and streaming. See PERFORMANCE_NOTES.md.
