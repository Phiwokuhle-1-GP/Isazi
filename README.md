# Isazi Herbal Shop — V2.6.16 Video Uploads & Mobile Hero

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

Stop Flask with Ctrl+C. Download Isazi_Herbal_Shop_V2_6_16_Rounded_Collection_Banner.zip into Downloads:

```powershell
cd "$HOME\Downloads"
Expand-Archive ".\Isazi_Herbal_Shop_V2_6_16_Rounded_Collection_Banner.zip" -DestinationPath ".\Isazi_Update_2616" -Force
powershell -ExecutionPolicy Bypass -File ".\Isazi_Update_2616\Isazi_Herbal_Shop_V2\APPLY_UPDATE.ps1"
if ($LASTEXITCODE -ne 0) { throw "Update failed." }
powershell -ExecutionPolicy Bypass -File ".\Isazi_Flask_Store\Isazi_Herbal_Shop_V2\START_WINDOWS.ps1"
```

The updater defaults to Downloads/Isazi_Flask_Store/Isazi_Herbal_Shop_V2. Use -TargetPath for another installed app folder. It backs up code and preserves runtime data. It never copies a packaged database or owner password. Press Ctrl+F5. /health must show version 2.6.16, demo_mode false and demo_payments_enabled true.

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

## Mobile and faster loading in V2.6.16

The phone layout has a collapsible accessible navigation menu, prominent search/cart/account controls, a compact swipeable category strip, a readable hero with its original photos, larger primary touch controls, phone-friendly forms and responsive order cards. Mobile quantity, gallery and menu interactions were checked in the browser. Customer and owner workflows remain the unified V2.6.5 journey.

Responsive WebP variants reduce delivery sizes while preserving original assets. The two original hero portraits are encoded losslessly with pixel equality checked. Small product/article images no longer request their full originals. User-uploaded images have cached bounded thumbnails; original uploads remain available. Videos/audio still use streaming range requests.

Static fingerprinted assets can be cached for a year, including in payment test mode. Personalized HTML/CSRF pages remain private and uncached. Text responses negotiate gzip. The original five stylesheets plus phone refinements are served in one versioned bundle. The asset build runs automatically at Windows startup and Render build/start, skipping work when inputs are unchanged.

See PERFORMANCE_NOTES.md for file-size measurements and validation limits. This update has not been deployed by creating the package; push it with the included Git script and verify the Render deployment.
