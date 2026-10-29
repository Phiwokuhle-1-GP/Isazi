# Isazi Herbal Shop — V2.6.4 Main Store Presentation

A standalone Flask e-commerce store with a long scrolling homepage, the original white navigation, forest-green and gold styling, high-resolution demonstration artwork, cart/checkout, order management and an owner workspace.

The hero is about 24% shorter on wide desktop screens (5:1 rather than 3.8:1). A muted meadow/misty-hills backdrop extends the setting of the original left photograph across the banner. Both people now use the supplied original photograph files directly. Display-only SVG cropping/masking places the right portrait onto the shared backdrop, with slightly reduced saturation and contrast; its face and clothing are not AI regenerated. The left photo's extra colour enhancement is removed. The subtle 10px / 8px corner rounding remains. Custom owner-uploaded full heroes remain selected without these default portrait overlays.

The story video now uses the latest supplied poolside photograph with its existing white play icon. The full scene is fitted proportionally into the video frame with dark green side panels; no duplicate play icon is added. It remains labelled Video coming soon until a real clip is added. Upload the clip in Owner → Media & Testimonials → Our Story. Existing custom covers and uploaded clips are retained. The About page uses the same backend story video and poster.

The header cart is now a shopping-cart icon with the live green quantity badge and an accessible cart/item-count label.

The hero portrait matte is refined around the shoulders and raised hand, with a soft edge and a narrow bottom fade into the landscape. Mild, matched CSS colour adjustments add a little warmth/colour to the background and both original photo layers. Source photo files and facial details are unchanged.

## Client demo journeys in V2.6.4

After updating, launch **START_DEMO_WINDOWS.ps1** for today’s presentation. It uses a separate `instance-client-demo/` database, stocked sample products and one-click sample customer accounts. Shop → product → Add to Cart → checkout → payment preview → demo receipt → My Orders works without external service credentials. Six clickable payment choices are supplied: Visa, Mastercard, Yoco, Ozow, PayFast and EFT. Success is explicitly simulated: no charges or transfers occur, and live PayFast/SMTP connections are disabled in demo mode. The normal store database, stock and owner account remain separate. Use START_WINDOWS.ps1 for normal store operation. See CLIENT_DEMO_GUIDE.md.

## Audio testimonials in V2.5.8

The four supplied cover images replace the built-in testimonial portraits. The section uses a yellow “Listen to testimonials” heading tile aligned with Health Tips. Repeated Audio testimony labels and generic default customer headings are hidden, and there are no Coming soon labels. Custom titles, captions and real audio controls remain. No actual recording was supplied, so the cards initially show their covers without repeated footer labels. Upload each real MP3/M4A/OGG/WAV (up to 50 MB) under Owner → Media & Testimonials, or provide its direct HTTPS file URL. Native audio controls appear after the recording is attached. Audio takes precedence over a legacy video; existing clips/covers and custom titles are preserved. Dr Ntuli’s story remains a video slot. No testimonial audio or quotes have been fabricated.

## What changed in V2.5

- Header Shop and shopping calls to action now open the full `/shop` catalogue with category sidebar, search and sorting.
- Product details add image galleries, quantity controls, information tabs and moderated verified-purchase reviews.
- Customer registration/login, private order history, saved addresses/items and password changes are included.
- Cart supports promotions; checkout captures approved agent attribution and preserves atomic stock checks.
- Owner Operations connects customer records, reports, approved agents, commission ledger/payout records, refunds, delivery tracking and notification drafts.
- Optional PayFast hosted checkout verifies server callbacks. Optional SMTP email sends require an explicit owner action. Both require configuration and are disabled until configured.
- Original white navigation, scrolling homepage, high-resolution demo assets and testimonial uploads remain.
- The homepage light green strip contains six category shortcuts above the hero. All categories remain available in Shop; management links and sign-out are on the Store dashboard.

Read **ECOSYSTEM_SETUP.md** for all routes, roles, payment/email configuration and operating limits. No real payment or outbound message was sent during development.

This build is for a client demonstration. AI product packaging and illustrative landscape assets are based on the supplied mockups. The hero portraits use the original supplied photographs, cropped and masked with a restrained colour adjustment. Packaging images are not verified product photography or confirmed labels, and testimonial covers do not establish health outcomes. Use your original approved media for public trading. The full asset list, native pixel dimensions and prompt briefs are in **DEMO_ASSETS.md**.

## Update your existing Windows installation

Stop the existing Flask process with **Ctrl+C**. Download `Isazi_Herbal_Shop_V2_6_4_Git_Push_Package.zip` and run:

```powershell
cd "$HOME\Downloads"
Expand-Archive ".\Isazi_Herbal_Shop_V2_6_4_Git_Push_Package.zip" -DestinationPath ".\Isazi_Normal_264" -Force
powershell -ExecutionPolicy Bypass -File ".\Isazi_Normal_264\Isazi_Herbal_Shop_V2\APPLY_UPDATE.ps1"
if ($LASTEXITCODE -ne 0) { throw "Update failed. Check the installation folder before starting." }
powershell -ExecutionPolicy Bypass -File ".\Isazi_Flask_Store\Isazi_Herbal_Shop_V2\START_WINDOWS.ps1"
```

The installer targets `Downloads\Isazi_Flask_Store\Isazi_Herbal_Shop_V2` by default. If your existing app is elsewhere, pass its real folder:

```powershell
powershell -ExecutionPolicy Bypass -File ".\Isazi_Normal_264\Isazi_Herbal_Shop_V2\APPLY_UPDATE.ps1" -TargetPath "C:\path\to\Isazi_Herbal_Shop_V2"
```

It backs up overwritten code under the target's `_update_backups` folder. It does not copy, replace or reset `instance/`, uploaded media, customer records, stock, owner credentials, the session key or `.venv`. New ecosystem tables are added automatically. Back up instance/ consistently before applying the update. Read ECOSYSTEM_SETUP.md for the one-time legacy payment-record migration. Do not recreate the owner during an update.

Open **http://127.0.0.1:5000/** and press **Ctrl+F5**. The startup text shows **v2.6.4**. **http://127.0.0.1:5000/health** also returns version `2.6.4`.

The updater was reviewed here, but no Windows PowerShell runtime was available to execute it. The Flask checks and browser preview used Linux.

## Fresh installation on Windows

For a client presentation, extract the package and run START_DEMO_WINDOWS.ps1; no owner setup is required for the sample customer journey. For normal store operation, follow the owner setup below.

Use Python 3.12. Extract the archive and open PowerShell in the inner `Isazi_Herbal_Shop_V2` folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\CREATE_OWNER.ps1
powershell -ExecutionPolicy Bypass -File .\START_WINDOWS.ps1
```

Choose an owner password of at least 16 characters. No password is shipped. Running CREATE_OWNER again resets the owner password.

If the `py` launcher is unavailable, use your Python executable:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app app create-owner
.\.venv\Scripts\python.exe app.py
```

The store opens at **http://127.0.0.1:5000/** and the owner sign-in at **http://127.0.0.1:5000/owner/login**. Keep the terminal open while presenting; Ctrl+C stops the local server.

## Short client-demo walkthrough

1. Present the homepage hero, category row, featured products and combo promotion.
2. Click **Testimonials** to scroll directly to the four audio-testimony cards beside the articles.
3. Show the lower promotions, product section and enquiry contact area.
4. Open the shop, search for a product and change the category/sort order.
5. If demonstrating checkout, ensure the demonstrated product has actual available stock in Owner → Edit product. New installations start with zero stock until the owner confirms availability.
6. Show the owner dashboard, product image upload, **Media & Testimonials** and **Home Images**. An existing owner can sign in without setting up a new account.
7. Any test order reserves stock. Cancel it in the owner dashboard afterwards to release the reserved units; keep actual stock accurate.

The supplied testimonial images are covers. Attach the actual customer recordings through Media & Testimonials to enable audio playback. No recordings, customer names or quotes have been invented. Existing custom covers and clips remain intact. The story slot continues to use the poolside video placeholder until the story clip is uploaded.

## Recommended replacement image sizes

| Location | Recommended source | How to replace |
|---|---|---|
| Desktop hero | 2400 × 800 px | Owner → Home Images |
| Optional mobile hero | 1200 × 1600 px | Owner → Home Images |
| Logo crest | 512 × 512 px, transparent PNG/WebP | Owner → Home Images |
| Product packshot | 1500 × 1000 px, 3:2 | Owner → Edit product |
| Combo photograph | 1500 × 1000 px, 3:2 | Owner → Home Images |
| Promotion photograph | 1500 × 1000 px, 3:2 | Owner → Home Images |
| Article cover | 1200 × 800 px | Owner → Home Images |
| Story video poster | 1600 × 900 px, 16:9 | Owner → Media & Testimonials |
| Testimonial poster | 1200 × 900 px, 4:3 | Owner → Media & Testimonials |

These are upload recommendations, not claims that all demo files share those exact dimensions. Native demo sizes are listed in DEMO_ASSETS.md: the hero is 2172 × 724 px, product/editorial pictures are 1536 × 1024 px, story cover is 1672 × 941 px, and testimonial covers are 1448 × 1086 px. They were generated at those native sizes and encoded as WebP; they were not enlarged from screenshot crops.

Use JPG or WebP for photographs. Use PNG/WebP with transparency for a crest. Maximum image upload is 10 MB and 20 megapixels. Homepage images are limited to 3200 px on the longest edge; product uploads to 2400 px and video covers to 2048 px. A below-recommended image is accepted with an owner-facing sharpness notice.

Keep faces, labels and bottles away from the edges. The desktop hero displays as a wide crop, so keep important details inside the central 600 px vertically. Use text-free photographs: hero and promotion headlines/buttons are live HTML. Product images use containment so the complete bottle or pouch remains visible. Article and video posters crop within fixed frames. The mobile hero falls back to the desktop image until a separate mobile image is uploaded.

## Uploading videos

Sign in and choose **Media & Testimonials**. There are five slots: Dr Ntuli's story video and four audio testimonials. For the story, upload MP4/WebM up to 100 MB or use a direct HTTPS .mp4/.webm URL. For testimonials, upload MP3/M4A/OGG/WAV up to 50 MB or a direct HTTPS audio-file URL. Choose a title and optional approved customer name/caption, then Save. Social-media page links are not direct media files.

A new upload takes precedence over its corresponding URL. Empty fields preserve the existing source. Remove Audio clears only the recording; Remove Video clears only the video. Neither deletes its cover or text. Unchecking Show on homepage hides that card. Files are retained for backup/recovery. Only publish recordings and customer details you have permission to share.

Audio testimonials show native playback controls after a real recording is attached; no Coming soon label is shown on the covers. A testimonial's audio takes precedence over a legacy video. The legacy video remains in the backend's collapsible section and can be cleared independently. Dr Ntuli's story plays as video on the homepage and About page; its dedicated media slot takes precedence over the older Store Settings video URL. No audio was supplied with the four images.


## Store and checkout behaviour

- Six initial sample products; names, pack sizes, ingredients, directions and prices require owner confirmation.
- Prices use integer ZAR cents and are recalculated on the server.
- Orders reserve stock atomically. Cancelled orders restore stock once and cannot be reopened. Unconfirmed orders have no automatic expiry; cancel stale reservations manually.
- Collection is free, with address arranged by the team.
- Randburg delivery is free on goods **over R600 after discounts**; net goods of **R600 or less** incur R50 delivery. Other areas require enquiry.
- Checkout defaults to manual confirmation. Optional hosted PayFast is available only after merchant configuration and public HTTPS callback testing; no card details are collected by the app.
- Private receipt links use random tokens. The receipt is an acknowledgement, not proof of payment.
- Contact enquiries are saved to the dashboard. Transactional notification drafts can be sent explicitly through configured SMTP; WhatsApp links open drafts for owner review.
- Product image/stock management, order statuses, CSV export, store settings and image/video editing are owner-only.

This version includes customer accounts and optional PayFast/SMTP connections. Courier booking, automatic WhatsApp sending, tax invoicing, automated password recovery and email verification are not implemented. Refunds and agent payouts record externally completed transactions; they do not transfer money. See ECOSYSTEM_SETUP.md. The R50 delivery fee is a starting assumption in app.py and shop.js; update both and the descriptions if changing it.

## Data, configuration and deployment

Data defaults to `instance/` and includes SQLite, uploads and a locally generated session key. Keep this folder private. Back up the database and uploads consistently; stop the app before copying the folder, or use SQLite's backup API for a live backup.

| Variable | Meaning |
|---|---|
| DATA_DIR | Persistent directory; defaults to instance/ |
| SECRET_KEY | Stable random Flask signing key; locally generated once if absent |
| COOKIE_SECURE | Set 1 for HTTPS hosting; leave unset for local HTTP |
| PORT | Local port, default 5000 |

The app does not automatically read .env files. `.env.example` is a configuration reference. The same app can run on Linux/macOS using a Python virtual environment, `pip install -r requirements.txt`, `python -m flask --app app create-owner`, and `python app.py`.

The archive includes Procfile and render.yaml for a Python web service. It has **not been deployed**. Render build command: `pip install -r requirements.txt`; start command: `gunicorn --workers 2 --bind 0.0.0.0:$PORT app:app`. Configure SECRET_KEY, COOKIE_SECURE=1 and DATA_DIR=/var/data with a persistent disk at /var/data. Create the owner through the hosting shell after deployment. Review the hosting plan before creating a service; no hosting purchase has been made.

Do not trade with ephemeral storage. The included blueprint requests a Starter service and 1 GB disk. The SQLite app is intended for one service instance; scaling requires a shared production database and object storage. Configure proxy-level throttling for a public store; the built-in login limiter uses the direct connection address. Never commit instance/, passwords, keys or customer data to Git.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The suite uses temporary databases. Demo checks cover all six payment previews, sample-account privacy, payment replay protection and separation from the normal store. **66 tests pass** across storefront, stock/checkout, uploads, videos, persistence, role isolation, customer accounts, promotion limits, agent commissions, refunds, payment verification/replays and notification delivery with mocks. No real payment or email was sent.

Shop, Product, Cart, Account, Contact and Operations were checked at six frame widths: 1911, 1366, 1024, 768, 390 and 320 px without document overflow. Quantity controls and product tabs were checked in the browser. Browser visual checks used Flask-rendered HTML because the preview host cannot run Python; backend actions used Flask's test client. No public deployment, real gateway transaction or SMTP delivery was tested. Windows PowerShell was reviewed but could not be executed here.

## Main files

- app.py — Flask routes, SQLite schema, image/video management and owner commands.
- templates/ — storefront, cart, checkout, receipts and owner screens.
- static/css/demo.css — V2.4 polish and white-navigation styling.
- static/images/demo-*.webp — native-resolution demonstration artwork.
- DEMO_ASSETS.md — asset dimensions, provenance and prompt briefs.
- ecosystem.py / payment_gateway.py — connected roles, operations and hosted payment verification.
- static/css/ecosystem.css — catalogue, product/account and operations layouts.
- ECOSYSTEM_SETUP.md — service configuration and operating guide.
- tests/ — 66 behavioural regression checks.
- APPLY_UPDATE.ps1 — code-only updater with backup and version verification.
- START_WINDOWS.ps1 / CREATE_OWNER.ps1 — local launch and credential setup.

V2.6.4 adds a soft green border around the four testimonial covers and matches the Listen to testimonials heading to the existing yellow buttons.

The footer includes WhatsApp and social icons. Add the Facebook, Instagram, TikTok and YouTube HTTPS profile URLs in Owner → Store settings; unconfigured profiles appear muted and do not link to unrelated accounts. Nationwide delivery is shown in the top banner, footer service strip and policy; outside Randburg, courier rates require a team quote before ordering.

V2.6.4 changes the banner to Free delivery on orders over R600. Checkout and its live total use the same strictly-over-R600 threshold; exactly R600 retains the R50 local fee. Nationwide delivery outside Randburg remains arranged by courier quote. Existing orders are unchanged.

V2.6.4 softens the right hero portrait edge and lower fade. RESET_OWNER_WINDOWS.ps1 prompts privately for a new password; use -ClientDemo for the presentation owner, omit it for the normal store owner. See CLIENT_DEMO_GUIDE.md.

V2.6.4: the latest storefront visuals, product/cart/account journeys, payment previews and owner controls are shared with normal mode. START_WINDOWS.ps1 explicitly starts normal mode; START_DEMO_WINDOWS.ps1 explicitly opts into the isolated demo. Render starts normal mode with a persistent disk and one threaded Gunicorn worker. Read PRODUCTION_HANDOFF.md before pushing/deploying.

## Today’s main-store presentation setting

START_WINDOWS.ps1 now uses the normal store database/owner and enables simulated payments with a PAYMENT TEST MODE banner. Owner and customer sign-ins are exclusive in each browser session. All six payment methods can simulate success on new test orders; these orders are visibly labelled and excluded from real financial totals/commissions. No live payment or email is sent. Test orders reserve normal stock: cancel them afterwards to release it.

Tomorrow, stop the process and use START_WINDOWS.ps1 -LivePayments to disable main-store simulations. On Render change DEMO_PAYMENTS_ENABLED from 1 to 0 and restart. This is a manual switch, not an automatic expiry. It does not configure real merchant credentials. The separate START_DEMO_WINDOWS.ps1 remains available. Read PRODUCTION_HANDOFF.md.

PUSH_GITHUB_WINDOWS.ps1 publishes to Phiwokuhle-1-GP/Isazi using your local GitHub sign-in. It verifies RELEASE_FILES.json, uses a clean separate Downloads/Isazi_Git_264 clone, pushes a backup branch first, and replaces the old tracked source in one normal commit without force-pushing. Runtime data/uploads/passwords are excluded. Run from the extracted package after applying the update to your installed store.
