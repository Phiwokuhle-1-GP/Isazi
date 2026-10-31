# V2.6.36 performance audit — 31 October 2026

Local changes only; not committed, pushed or deployed.

## Baseline and measured changes

| Measure | V2.6.35 | V2.6.36 | Change |
|---|---:|---:|---:|
| Homepage default image references | 1,743,162 bytes | 1,286,338 bytes | 26.2% smaller |
| Homepage eagerly marked image references | 792,422 bytes | 769,704 bytes | 2.9% smaller |
| Browsing-page JavaScript references | 14,531 bytes | 12,581 bytes | 13.4% smaller; one fewer request |
| Homepage responsive img elements | 14 | 21 | 7 more adapt to screen size |

## Changes

- Combo and promotional images now provide responsive source sets instead of always defaulting to the largest image. Testimonials have 320/640 pixel choices. Phones and desktop browsers can select a suitable asset using viewport size and pixel density.
- Story preview poster is lazy loaded, with intrinsic dimensions supplied. Video playback remains click initiated.
- Header and footer use the existing optimized logo. Custom crests request a bounded image size.
- Phone checkout JavaScript loads on checkout, customer registration and phone checkout settings pages, rather than every browsing page. Payment-step registration and PEP selection retain their controller.
- Layout/CSS, original portraits, product data, owner access and payment operations are unchanged.

## Method and limits

Repeat with `python tools/performance_audit.py` from an installed development environment. The script creates and removes an isolated temporary database; it does not modify store data. Raw before/after results are in tools/performance_baseline.json.

These are local code/payload measurements, not Lighthouse scores or real network transfer counts. Totals deduplicate default img src and SVG image href URLs; they do not model picture sources, srcset choice, CSS images, lazy-loading distance or browser cache. CSS, fonts and video are outside the image totals. Lazy loading defers work; it does not eliminate all eventual downloads. Responsive selection can use larger files on high-density screens.

HTML grows slightly from the responsive attributes (about 0.1 KB compressed on Home). Warm local response times remain a few milliseconds and are not comparable to live Render latency. No claim is made for improved LCP, INP, CLS or seconds-to-load until the live URL is measured on mobile and desktop. Cold Render starts, uploaded media and real database size are not measured here.

Validation: all 123 pre-existing automated tests passed. The new scoped-script test initially had a test-helper error, corrected before rerunning the performance suite. The five performance tests pass after correction. Original portrait pixel-preservation, gzip/cache, upload range and private-page cache tests remain passing. No new visual browser audit was performed for this patch.

## Live baseline — 31 October 2026

URL: https://isazi-herbal-shop-client-portal.onrender.com/

Health endpoint reports V2.6.35 and status ok. Home responds HTTP 200 and renders in the remote browser. This verifies baseline deployment, not the local V2.6.36 patch.

- Homepage HTML: 35,496 uncompressed bytes; 6,641–6,642 compressed bytes (about 81% reduction already enabled).
- CSS: 27,610 compressed bytes; fingerprinted URL with public max-age=31536000, immutable.
- Desktop hero background: 287,392 WebP bytes; public one-year immutable caching.
- shop.js: 4,040 compressed bytes; public one-day caching.
- Personalized HTML: private, no-store.
- Three independent curl requests: TTFB 7.235, 7.226, 8.355 seconds; connection/TLS completion 7.040, 7.035, 8.169 seconds. Difference approximately 0.195, 0.191, 0.186 seconds. These are remote test-network observations, not isolated server processing or browser rendering times. The large connection overhead makes the raw totals unsuitable as customer load-time estimates.

Google PageSpeed API returned HTTP 429 quota exhausted. The browser inspection API did not expose Performance entries. Consequently mobile/desktop Lighthouse, LCP, CLS, INP and full browser load times are unmeasured. No mobile score is inferred from desktop HTTP requests.

Next comparison requires the same browser/device/network profile after V2.6.36 deployment. Local image-byte savings remain separate from live baseline measurements.
