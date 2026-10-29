# V2.6.6 Mobile and performance verification

## Delivered changes

- Compact mobile header with an accessible expandable menu, search, account and cart controls. Menu supports keyboard Escape and closes after selection; no-JavaScript store links remain available.
- Phone hero uses the landscape/portraits above readable copy and buttons; the missing space in "your health" is fixed. Category links swipe within their own strip.
- Larger primary touch controls and 16px form inputs. Checkout reflows into one column; customer orders become labelled cards. Desktop styling remains intact.
- Responsive WebP images and lazy/asynchronous loading below the hero. Gallery selections clear the original responsive source set so the chosen picture actually appears.
- The two original hero portraits retain identical decoded pixel data and dimensions through lossless encoding. Their original source files are kept.
- Fingerprinted static files cache publicly for a year. Personalized HTML remains private/no-store. Gzip is negotiated and respects gzip;q=0. Range responses and original uploads are preserved.
- Uploaded image thumbnails are bounded to 320/640/1280 widths and cached beside uploads. Large original files are retained and not regenerated on every request.
- One stylesheet bundle replaces five separate CSS requests. The mobile refinements are included in the bundle. The default script remains deferred.

## Measurements

Unique default img/src and inline SVG/image href sources in the rendered homepage totalled 6,381,688 bytes before and 1,668,448 bytes after optimization: 73.9% fewer referenced image bytes. This sums file sizes for those default URLs; it is not an actual download trace. Responsive image selection, screen density, lazy loading and existing browser cache can change the files a visitor requests.

The combined stylesheet is 89,876 bytes before compression and 18,571 bytes with the configured gzip compression level. It needs one normal stylesheet request; the source CSS files remain for editing/fallback.

No Lighthouse score or real-world seconds-to-load claim is made. Actual network latency, Render startup, device CPU and uploaded media affect the result.

## Verification

74 automated checks pass, including the entire registered-customer dry run, owner purchase blocking, saved orders/payment receipts, persistence, cancellation stock pools, owner reports, image upload/streaming handling, gzip negotiation, conditional caching, source-photo pixel equality and thumbnail cache reuse.

Browser QA checked 15 pages over 10 phone/tablet/desktop iframe sizes (150 checks) without horizontal document overflow. Pages included Home, Shop, Product, Cart, Checkout, Payment, Receipt, Registration, Customer Login, Account, About, Contact, Health Tips, Tracking and Owner Login. Browser scrollbars reduce the actual content area within an iframe. Mobile menu, Escape, gallery replacement and quantity controls were exercised separately. These checks use exported Flask-rendered HTML; server-side forms and purchases use Flask test clients. Actual phone hardware and a live Render performance audit were not available here.

## Build and deployment

Run optimize_assets.py after changing source images/CSS. START_WINDOWS.ps1, render.yaml and render_start.sh invoke it automatically; unchanged input fingerprints skip rebuilding. asset_manifest.json selects generated files under static/optimized. The source archive keeps originals and only the currently referenced generated assets.

Deploy the updated code and confirm /health returns 2.6.6. A new asset filename invalidates the old cached version. No database reset is needed. Accounts, uploaded media, real/test stock, stored test orders, payments and owner access are preserved. Keep the persistent Render disk attached. Use DEMO_PAYMENTS_ENABLED=1 for the current dry run; switch to 0 separately when ready. Neither optimization nor that switch configures a live payment provider.
