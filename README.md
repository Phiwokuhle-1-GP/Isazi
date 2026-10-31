## V2.6.35 — Visual reference alignment

Shared green/cream/yellow treatment across shop, products, cart, checkout, accounts, owner dashboard, contact and editorial pages. Mobile category chips, clearer cart cards, botanical sign-in panel, yellow purchase actions, rounded images. Existing desktop layout, prices, cellphone/PIN registration and payment processing retained.

## V2.6.30 — Product photo update

Replaces the two narrow portrait photos with landscape botanical product photos. Updates responsive WebP images and card fitting for desktop and mobile. Product names, prices and owner data remain unchanged.

## V2.6.29 — Two new products

Adds Nyawozeni (R150) and Soursop Leaves (R120), using the supplied photographs. Best Sellers now has eight default products in two desktop rows of four. Existing store data and subsequent owner edits are preserved. Actual stock remains owner-controlled; test inventory remains available for the dry run.

# V2.6.29 — Product testimonial covers and audio playback

Approved product cover order: Smolo, Mashamba, Herbal Combo, Smolo. Built-in covers/titles migrate; custom owner covers are preserved. New testimonial video uploads extract AAC mono 96kbps M4A only; originals are private and temporary, and no new video rendition is published. Videos without audio fail without changing the existing recording. Direct URLs and legacy videos can play through the audio player but are not recompressed: re-upload them for audio-only smaller files. Listen/Pause buttons retain product images and expose native seek controls. Story videos remain full video. Best Sellers displays up to eight active catalogue products with four columns on desktop; six existing products currently give four plus two. Two additional real products are needed for a full four-by-two grid. Mobile retains sideways scrolling. Includes all previous updates.

# V2.6.27 — Heritage banner

Adds the supplied traditional-attire portrait and heritage banner below Our Partners, beside Best Sellers on desktop and before Contact on mobile. Explore Our Heritage links to About Dr Ntuli. Includes all V2.6.26 checkout and playback fixes.

# V2.6.26 — Account details at payment

Browsing, cart additions and bundle Buy Now no longer require registration. Checkout first shows payment/delivery choice; cellphone/PIN fields appear after choosing. PEP branch preference and cart/bundle are retained through registration. Existing customers sign in and return to checkout. Full name and final order confirmation follow; guest order submission stays blocked when customer accounts are required. Includes V2.6.25 story playback and earlier updates.

# V2.6.25 — Click story preview to play

The complete story preview is a keyboard-accessible play button on home and About. It selects the first active story with a playable source, skipping empty slots. Opens the player and starts playback using the mobile rendition on phones. Watch Our Stories still opens the library. Without a published video the preview links to the empty library. Includes previous updates.

# V2.6.24 — Navigation and story preview

Removed the coming-soon overlay from homepage and About story previews. Slightly taller navigation on desktop and mobile, preserving the existing layout. Includes the story video library and all previous changes.

# V2.6.23 — Story video library

Watch Our Stories opens /videos on desktop and mobile. Owner > Media supports selecting multiple MP4/WebM files, sent sequentially (250 MB each). Each is published only after desktop 720p and mobile 480p H.264/AAC conversions finish. Originals transfer privately to server scratch storage before compression; this is not browser-side compression before network upload. Source originals are removed after conversion. CRF 23 / fast encoding balances visual quality and size; compression is lossy and size reductions depend on the source. Native playback, fast-start MP4, and mobile rendition selection are retained. Direct HTTPS video links bypass transcoding.

Titles default to filenames. Refresh owner Media to edit titles, covers or hide videos. Supplied Dr Ntuli portrait is the default library cover. Existing story and audio testimonials remain. A failed file does not block other files; on connection loss check the library before retrying. No background job resumes uploads after closing the page. The existing bounded conversion limit remains 4 minutes per rendition; long videos may need shorter clips. Not deployed.

# V2.6.22 — Dr Ntuli video preview

Uses the supplied portrait as the story video poster on the homepage and About page, including the video dialog. Existing videos and controls remain unchanged. Includes all previous updates.

# V2.6.21 — Compact mobile footer

Phone footer now uses a compact wordmark, contact row, expandable Explore and Customer care menus, social icons and copyright. Links retain 44px touch targets. Desktop footer unchanged. Includes all prior updates.

# V2.6.21 — Header attribution

Header branding now reads “by DR NTULI” on desktop and mobile. Includes the previous bundle quick-purchase and order notification updates.

# V2.6.21 — Order notifications & QR codes for every product

1. Place a PEP order: it stays Awaiting confirmation; a pending notification is saved.
2. Owner verifies the full Capitec receipt and confirms payment: a payment-confirmed notification is saved. Duplicate confirmations do not duplicate payment records or messages.
3. Owner records dispatch and the PAXI tracking reference: a dispatch notification is saved. Ready-for-collection updates generate a separate message. PAXI, not this app, provides the collection PIN when the parcel is available. Never send the customer's account PIN.
4. Real order notifications send automatically after commit when SMS is configured and enabled. Unconfigured messages stay in the owner outbox; provider timeouts stay held for manual reconciliation. No automatic retry, background worker or delivery-receipt callback exists. SMS provider calls can add up to 15 seconds to the initiating request. If a process stops after commit but before sending, the message remains available for owner review/send. Test notifications are saved and visible, but never sent.
5. Customers can read their notification history on their private order page, even without SMS delivery. The owner sees provider acceptance / queued / test status. Acceptance is not a handset-delivery guarantee.
6. Only products marked Bundle deal have QR endpoints and quick-purchase links. The existing Herbal Combo Pack is enabled during migration; mark future bundles in the owner product editor. Mobile bundle cards show Buy Now, and tapping the bundle image/name starts quick checkout. QR codes are hidden on mobile and offered on desktop. Ordinary products retain Add to Cart and reject direct QR/quick-purchase requests. Owner > Bundle deal QR codes offers downloads for active bundles. Configure the public HTTPS shop URL first; QR destinations are never guessed from an untrusted request Host header.

Validation: automated checkout, owner confirmation, no duplicate receipts/messages, SMS test isolation, provider failure handling, bundle-only QR coverage and owner access restrictions. Live bank transfers, live SMS and camera scanning against a deployed public URL still require rollout checks. This package is not deployed.

# Isazi V2.6.21 — Cellphone, PEP pickup & product QR

## New customer journey
- New accounts use a normalized South African cellphone number and a salted/hashed 4-digit PIN. The immutable database customer ID is linked to the unique phone number; the displayed ID is ISZ-C followed by seven digits. Existing email/password accounts remain supported and are never silently merged.
- Account-level lockout after five failed PIN attempts, even across IP addresses; ten failed attempts lock for a day. IP throttling is also enforced. Phone number changes/PIN recovery require staff-assisted identity checks; no automatic SMS ownership verification or self-service recovery is implemented in this release. Never reset an account based only on a caller knowing a number.
- Choose PEP pickup + Capitec transfer or other delivery/collection + the existing gateway journey. Recipient name is collected at checkout, email is not required for phone accounts.
- PEP branches: 2,487 open South African PEP-family locations from https://map.paxi.co.za/points.json, fetched 30 October 2026. This is a dated directory snapshot, not a live booking integration. Closed, planned and hold locations were excluded. Confirm the destination with the official PAXI locator at dispatch.
- Delivery is free strictly OVER R600, after discounts. Set the fee for R600 or less under Owner > Cellphone checkout. Smaller PEP orders are blocked until that fee is configured.
- Set the shop's verified Capitec holder, number, type and branch code in the same screen. Banking details are frozen on new orders. Existing orders created without banking settings need staff to supply verified instructions.
- Orders stay awaiting payment. Owner must explicitly confirm the full bank receipt with a bank transaction reference before dispatch. A cellphone reference identifies the customer, not a unique transfer: reconcile each order/amount separately when a customer has multiple pending orders. Confirming twice never adds a duplicate receipt. PEP orders cannot use demo or PayFast payment endpoints.
- Dispatch requires a PAXI tracking reference. A durable SMS outbox appears on the order. Pending, payment-confirmed, dispatch and ready-for-collection messages are saved durably with each order event. For live orders, configured/enabled SMS sends automatically after the transaction commits. Without SMS configuration they remain Queued and can be sent by the owner. No automatic booking or bulk send. Twilio is supported: configure the Account SID, Auth Token and registered sender privately in the owner settings. Token is never rendered back or put in public context. Provider acceptance is recorded, not claimed as handset delivery. An uncertain timeout is held for manual provider reconciliation, with no blind retries.
- PAXI sends its own collection OTP on arrival; it is not the Isazi login PIN. Isazi dispatch messages do not manufacture collection PINs.
- Payment-test orders stay simulated, never show bank transfer instructions and never send real SMS. Normal/live mode uses the store stock pool and real finance records. Changing modes does not convert earlier orders.

## Product QR quick purchase
Set the public HTTPS homepage address in Owner > Cellphone checkout, or PUBLIC_BASE_URL. Each bundle page shows a downloadable black-on-white QR PNG on desktop and Buy Now on mobile. Bundle QR contains only the public /buy/<product_id> link, no account/payment credentials. It opens one-unit checkout for that product (bundles use their own product ID). New users register first and retain that product. Existing basket items are preserved separately. Prices, stock and totals are revalidated at order placement. QR must be tested on a phone against the actual public URL before printing.

## Update / deployment status
This release was prepared and tested locally. It has NOT been pushed or deployed. Use the included updater on the installed Windows application; data/accounts/orders/uploads are preserved. Configure bank, fee, shop URL and SMS before a real rollout. Existing payment providers remain in the previously configured test/live mode.

# Isazi Herbal Shop — V2.6.21 Mobile & Desktop Storefront Refresh

The approved design refresh uses locally hosted Manrope fonts, rounded cards, yellow primary actions, original branding and swipeable mobile product/testimonial/article rails. Desktop keeps the existing section order and columns. The customer login, cart, checkout, payment and account pages share the new theme. The desktop featured row shows five products; all six remain in the mobile carousel and shop. Actual media, product details, stock and account/payment logic remain authoritative. No deployment is performed by this update.

One storefront, one owner backend and one database. Start START_WINDOWS.ps1. The compatibility launcher START_DEMO_WINDOWS.ps1 now starts this same site. Owner reset scripts also target this same store. Existing normal-store accounts, orders, uploads and real stock are preserved.

The mobile category strip above the hero is hidden; desktop categories remain visible. The gold test-mode banner is removed from customer browsing pages.

New video uploads are converted before publishing to desktop 720p and mobile 480p MP4 versions. On mobile, the hero is hidden and The Herbal Collection card appears first below navigation, followed by About Dr Ntuli. The mobile footer groups the brand, links and contact details with consistent spacing and touch targets. Desktop retains the hero and original section sequence. Featured products display six cards to complete the two-column mobile grid. See VIDEO_UPLOADS.md for upload limits and processing details.

## Dry-run behaviour

- The main site uses simulated payments without a global test-mode banner. Checkout and receipts still identify simulated payments. New products have 50 test units stored separately from real stock; active products with test stock show Add to Cart immediately. Test stock persists and reduces when test orders are submitted. Owner → Edit product can change test stock.
- Customers create a real customer account or sign in before adding to cart or checking out. A registration prompted by a product returns to that product. Shop → product → cart → checkout → six simulated payment methods → receipt → My Orders is complete.
- Owners can browse/manage but cannot add to cart, change a cart, check out or complete a payment. Owner sessions block customer sign-in/registration until sign-out. Use another browser profile/incognito window for the customer when demonstrating both roles at once.
- All dry-run orders and their customer links, quantities, payments and statuses are saved in the normal database. Owners see them in Recent orders, the saved-test-orders KPI, simulated receipts and Reports → Test orders / dry run. They can mark Ready/Completed or cancel. Cancellation restores the original stock pool once, including after changing payment mode.
- Test payments never contact a bank/provider. Each receipt is labelled CLIENT DEMO / method, and each order is marked Payment test. They are excluded from real financial reports, commissions and verified-purchase reviews. Dry-run reports separately include them. They do not enter the email outbox.
- Real stock is not changed by new test orders. Previously created V2.6.4 test orders reserved real stock; their original stock pool is preserved so cancellation restores the correct units. No existing order/account/payment record is reset.

## Update an existing Windows installation

Stop Flask with Ctrl+C. Download Isazi_Herbal_Shop_V2_6_21_Compact_Mobile_Footer.zip into Downloads:

```powershell
cd "$HOME\Downloads"
Expand-Archive ".\Isazi_Herbal_Shop_V2_6_21_Compact_Mobile_Footer.zip" -DestinationPath ".\Isazi_Update_2621" -Force
powershell -ExecutionPolicy Bypass -File ".\Isazi_Update_2621\Isazi_Herbal_Shop_V2\APPLY_UPDATE.ps1"
if ($LASTEXITCODE -ne 0) { throw "Update failed." }
powershell -ExecutionPolicy Bypass -File ".\Isazi_Flask_Store\Isazi_Herbal_Shop_V2\START_WINDOWS.ps1"
```

The updater defaults to Downloads/Isazi_Flask_Store/Isazi_Herbal_Shop_V2. Use -TargetPath for another installed app folder. It backs up code and preserves runtime data. It never copies a packaged database or owner password. Press Ctrl+F5. /health must show version 2.6.21, demo_mode false and demo_payments_enabled true.

## Owner and customer walkthrough

Use /owner/login for management. Reset this owner privately with RESET_OWNER_WINDOWS.ps1; passwords require 16 characters. The owner cannot purchase. Sign out in the dashboard, then use /account/register or /account/login to shop. Keep both roles in different browser profiles if presenting them together.

For each product review the image, quantity, Add to Cart and Back to Shop. Submit a cart, select delivery/collection, consent and continue to a payment method. Simulate success; the receipt and My Orders show the saved test order. Return to the owner profile to view/fulfil/cancel the same order. Reports → Test orders / dry run shows its simulated financial figures. Restart the app to confirm persistence.

## Images, recordings and social profiles

The shorter meadow hero retains the original portraits with masked/softened edges. Testimonial covers are grouped inside a border with the yellow Listen to testimonials heading. Owner → Home Images replaces imagery. Owner → Media & Testimonials uploads MP3/M4A/OGG/WAV recordings up to 50 MB and story MP4/WebM up to 250 MB, or direct HTTPS media URLs. The supplied covers are placeholders; no real testimonial recordings are included. Existing uploaded files remain.

Owner → Store settings manages contact information, delivery text, policies and Facebook/Instagram/TikTok/YouTube HTTPS links. WhatsApp uses the store phone. No social profile is invented. Product images and some landscape assets are illustrative; the hero portraits use the supplied original photos. See DEMO_ASSETS.md for the asset inventory.

Free delivery is strictly above R600. Automated rates remain collection free and Randburg R50 at/below R600, free above R600. Other South African areas require a team courier quote before ordering. No courier booking API is connected.

## Git and Render

PUSH_GITHUB_WINDOWS.ps1 validates RELEASE_FILES.json and publishes from a separate Downloads/Isazi_Git_266 checkout to Phiwokuhle-1-GP/Isazi. It pushes a backup branch first, replaces tracked source in one regular commit and verifies main. No force push is used. Local customer databases/uploads/passwords are excluded. GitHub must authorize your local Git sign-in.

The Render blueprint keeps the existing service name and disk. render_start.sh supports the existing bash startup command and legacy secret/HTTPS variable names. The normal database is /var/data/shop.sqlite3; old portal data /var/data/isazi.sqlite3 remains separate. Create the shop owner via the Render Shell, not a committed password. See PRODUCTION_HANDOFF.md.

## Finish the dry run

To disable simulated payments, stop the process and use START_WINDOWS.ps1 -LivePayments. On Render set DEMO_PAYMENTS_ENABLED=0 and restart/redeploy. This is a manual switch. Customers then use actual stock and only independently configured real payment services. Existing test orders remain saved and labelled; test reports stay available. Customer registration remains required. No payment provider is configured by this switch.

## Verification

All 74 automated checks pass. The suite uses temporary databases to verify shopping, access roles, uploads, simulated and verified payment handling, inventory, persistence, cancellations, reporting and existing records. Browser checks use Flask-rendered HTML; backend checks use Flask's test client. Windows PowerShell and live Render/provider connectivity must be verified on those systems. Source archives exclude databases, uploads and owner passwords.

## Mobile and faster loading in V2.6.21

The phone layout has a collapsible accessible navigation menu, prominent search/cart/account controls, a compact swipeable category strip, a readable hero with its original photos, larger primary touch controls, phone-friendly forms and responsive order cards. Mobile quantity, gallery and menu interactions were checked in the browser. Customer and owner workflows remain the unified V2.6.5 journey.

Responsive WebP variants reduce delivery sizes while preserving original assets. The two original hero portraits are encoded losslessly with pixel equality checked. Small product/article images no longer request their full originals. User-uploaded images have cached bounded thumbnails; original uploads remain available. Videos/audio still use streaming range requests.

Static fingerprinted assets can be cached for a year, including in payment test mode. Personalized HTML/CSRF pages remain private and uncached. Text responses negotiate gzip. The original five stylesheets plus phone refinements are served in one versioned bundle. The asset build runs automatically at Windows startup and Render build/start, skipping work when inputs are unchanged.

See PERFORMANCE_NOTES.md for file-size measurements and validation limits. This update has not been deployed by creating the package; push it with the included Git script and verify the Render deployment.

## Video preview cleanup
The story player now loads video metadata without the uploaded poster, removing the large play mark from that poster. The decorative story placeholder play overlay is also removed. Native playback controls remain. Marks baked into video frames cannot be removed by this template change; those require the clean source video.


## Local owner workspace update — V2.6.35

Based on GitHub main c5cfb1398b84a1507cd7cc4a0db947e302e6f38a. No deployment performed.
New grouped sidebar, mobile drawer/bottom navigation, focused orders/products/enquiries views, real/test filters, low-stock filter, 30-day receipts trend and real payment/dispatch attention counts. Other owner forms retain their existing endpoints, CSRF protection and validation.
Recorded receipts are gross recorded payments, before refunds; not net revenue or a bank reconciliation. KPI counts are all-time; the trend covers the last 30 UTC calendar days. Active products below five real-stock units count as low stock. Dispatch count includes real Paid/Ready orders whose delivery is Not arranged, Booked or Payment confirmed. Test receipts are separate.
Stop the running local server with Ctrl+C. Extract this ZIP, run APPLY_UPDATE.ps1 with the existing local app folder as -TargetPath, then START_WINDOWS.ps1 in that app folder. Verify /health reports 2.6.35 and hard refresh the browser. The updater backs up code and preserves the database, stock, orders, owner password and uploads. Do not run PUSH_GITHUB_WINDOWS.ps1 for local-only testing.
Validation: 123 automated tests passed, including real/test separation, receipt aggregation, dispatch and low-stock filters, access controls and existing payment workflows. Desktop and 390px mobile Flask-rendered pages inspected in browser; mobile drawer opened/closed. Backend requests verified by Flask test client; Windows PowerShell installer must be run on the user's PC.
