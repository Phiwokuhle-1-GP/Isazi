# Isazi security audit — 31 October 2026

Scope: local Flask source based on V2.6.35 plus the V2.6.36 performance changes. Read-only source review and adversarial requests against disposable test databases. No attack traffic, account guessing or purchase submissions were sent to production. Security changes are packaged in V2.6.37 with the V2.6.36 performance improvements retained. The previously supplied V2.6.36 performance ZIP did not include these security fixes. Deployment must be verified separately.

## Confirmed findings and local fixes

| Finding | Severity | Evidence and fix |
|---|---|---|
| Non-ASCII CSRF and checkout tokens caused TypeError | Low (availability) | Reproduced exceptions using Unicode tokens. Inputs now have bounded length and ASCII validation before constant-time comparison; invalid requests return 400. |
| Non-ASCII payment signature caused TypeError | Low (availability) | Signature helper reproduced an exception, not payment acceptance. Require a 32-character ASCII signature before comparison; bad signatures fail closed. |
| Public forms inherited the 312 MB media-upload allowance | Medium (resource exhaustion) | Anonymous requests shared the video body limit; hashing inputs lacked a common upper bound. Public requests now cap at 64 KiB, credentials at 256 characters, query strings at 8 KiB, query values at 4096 characters, form values at 16384 characters, and parameter counts at 64. Multipart fields cap at 128 KiB and parts at 64. Large bodies remain available only to authenticated owner upload endpoints. |
| Duplicate scalar parameters silently used the first value | Low (ambiguous input) | A duplicate cart quantity was accepted; no price or privilege bypass was demonstrated. Duplicate query/form text keys now return 400 before mutation. Repeated gallery file fields remain supported. |
| Resetting owner password did not revoke existing signed sessions | Medium | Owner session contained only an admin boolean. Session now records a SHA-256 fingerprint of the stored salted password hash, verified against current database state on every request. Password reset invalidates previous owner sessions. Existing owners must sign in again after deployment. |
| Malformed bracketed URL input could raise ValueError | Low (availability) | Tracking and configured public URLs could throw during URL parsing. Tracking inputs now return 400; invalid public URLs disable the integration without breaking the homepage. |

## Controls reviewed

- Shop search/category use bound SQL parameters; sort uses a fixed mapping. Owner filters append predefined SQL fragments and bind their values. Dynamic stock column names originate from fixed real/test choices, not raw client input.
- Prices and order totals are calculated from server-side product data; quantities and stock are validated. Existing transactional stock and duplicate payment tests pass.
- Owner routes use owner authorization decorators. Customer address and order-claim tests enforce customer identity or the receipt token. SQL/XSS probes, unauthenticated owner access and traversal attempts are covered locally.
- CSRF remains required for POST operations. PayFast notifications remain the deliberate exception, with independent signature, merchant, source IP, amount, server-validation and duplicate-event checks. A browser payment-return query is not payment proof.
- HTML templates use autoescaping. Tested injected search text did not execute or appear as a raw script. CSP and nosniff headers remain enabled.
- Image uploads use generated filenames and image decoding/re-encoding. Media serving uses send_from_directory; thumbnail sizes have a fixed allowlist. Video transcoding uses argument arrays, not a shell command string.
- Customer and owner credentials are hashed. PIN sign-in has account lockout as well as IP throttling. Customer auth-version invalidation remains intact.
- Personalized HTML remains non-publicly cached; deployment blueprint sets Secure/HttpOnly/SameSite cookie protections and a generated session secret.

## Remaining risks and deployment checks

1. Four-digit PINs have only 10,000 combinations. Rate limits reduce online guessing risk but do not make a PIN equivalent to a strong password. Phone registration does not verify possession via OTP. Consider SMS verification for registration/recovery; it was not added without a verified provider and an agreed customer flow.
2. No TRUSTED_HOSTS configuration is enforced by the current app. External payment links use a separately validated configured public URL, which limits the obvious exposure. Configure an exact allowlist after confirming every production/custom domain and health-check host; do not blindly restrict hosts and break deployment.
3. Owner/email/agent login throttling uses remote_addr. Correct client identity and upstream rate limiting behind Render need infrastructure verification. Do not blindly trust forwarded headers.
4. Order receipt URLs are bearer credentials by design. Anyone holding a valid receipt link can view that receipt. Token entropy is high, but protect these links in messages, logs and referrer handling.
5. No dependency CVE scan, infrastructure penetration test, TLS configuration review, secrets inventory or authenticated live security audit was performed. Production environment values were not exposed or modified. This is not a certification that all parameters or attack surfaces are safe.
6. Production previously reported demo payments enabled. Keep simulated payment flows clearly separated from real receipts; enabling real payment collection is a separate configuration task.

## Verification

New tests in tests/test_parameter_security.py reproduced five failing cases before fixes (three exceptions and two validation failures). The final dedicated suite contains ten passing tests, including owner password-reset revocation and an authenticated PNG upload larger than the public limit. Final full regression run: 134 tests passed in 46.535 seconds. git diff --check passed.

Reference: Flask's official security guidance on request limits and trusted hosts: https://flask.palletsprojects.com/en/stable/web-security/
