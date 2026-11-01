# V2.6.38 — payment choice before cellphone access

Prepared 1 November 2026 against Git main commit `352b951`. Local patch only; no commit, push, merge or Render deployment was performed.

## Customer journey

1. Cart or enabled bundle Buy Now leads to four payment choices: Card, Paystack, Ozow and PEP pickup + bank payment. There is no standalone bank-transfer choice in the new list.
2. Selecting a method and pressing Continue opens cellphone registration or sign-in. Registration collects cellphone number, four-digit PIN, PIN confirmation and privacy consent. A customer already signed in proceeds directly to the next step.
3. PEP customers select their branch and provide their name. Gateway customers choose delivery or collection. PEP is not offered inside the gateway delivery form.
4. The customer reviews calculated delivery charges and total, then creates the order. Server-side pricing, stock reservation, branch validation and checkout idempotency remain authoritative.
5. A PEP order shows Capitec instructions and the customer's cellphone reference, pending owner verification. Existing owner confirmation, payment records, dispatch guards, SMS outbox and PAXI collection instructions remain in use. Account PINs and PAXI collection PINs are different.
6. In payment test mode, the selected gateway opens its simulated screen directly, without another method-selection step. Test receipts and notifications remain identified as tests; they never send a real payment or SMS.

## Provider availability

The site has an existing PayFast hosted-card adapter. Card is offered for real checkout only when that adapter is ready. Paystack and Ozow have presentation/test screens only in this patch. Their real-payment choices are disabled, marked Not connected yet, and rejected on the server. No real Paystack/Ozow integration or credential setup is claimed. Raw card numbers and security codes are not collected by Isazi.

Existing legacy simulation URLs remain available for older test receipts. The isolated legacy Client Demo mode retains its sample-customer behavior; the revised cellphone flow applies to the normal store, including its payment-test configuration. No real-payment environment flags or credentials are changed by the installer.

## Design

Responsive white and cream panels, forest-green selected states, yellow primary actions, progress navigation, order thumbnails, and a compact cellphone form. PEP confirmation screens distinguish awaiting payment, payment received, in transit and ready for collection. This implements the approved sequence and treatment using existing branding and product imagery; it does not substitute generated packshots or logos into the store.

The browser available during development could not reach the local server. Flask regression tests and rendered-HTML checks passed; manual desktop/mobile browser verification is still required before any deployment. Check tab order, phone keyboards, branch filtering, validation errors, totals, narrow screens and payment-test labels locally.

## Install locally on Windows

Stop the running Flask server with Ctrl+C first. Extract the ZIP. In PowerShell run:

```powershell
$patch = "$HOME\Downloads\Isazi_Checkout_V2_6_38"
$target = "$HOME\Downloads\Isazi_Git_2634_retry_20261031_114226"
python "$patch\APPLY_CHECKOUT_PATCH.py" --target "$target" --check
python "$patch\APPLY_CHECKOUT_PATCH.py" --target "$target"
cd "$target"
powershell -ExecutionPolicy Bypass -File .\START_WINDOWS.ps1
```

If using the existing local app instead of the Git checkout, set `$target` to `$HOME\Downloads\Isazi_Flask_Store\Isazi_Herbal_Shop_V2`. The installer checks all affected code before writing and refuses to replace an unexpected version. It creates a timestamped code backup in `_update_backups`. Database, uploads, product contents, bank settings, stock and orders are not copied or replaced. An additive table for each order's selected payment method is created at app startup.

The ZIP also includes `checkout.patch` for developer review. The installer is the recommended Windows route because it accepts CRLF and UTF-8 BOM differences. Use it once per target. Rerunning an already applied patch is harmless.

Visit http://127.0.0.1:5000/health and confirm version 2.6.38, then test checkout in a private browser window. The startup script uses payment test mode by default. For a configured PEP fee or bank details, use the existing owner Cellphone checkout & PEP settings. Never transfer real money for a test order.

## Validation

The existing 134-test regression suite passed after adapting checkout expectations to the new sequence. Additional checkout tests cover choice-before-auth, registration without premature branch selection, returning-customer sign-in, selected card/Paystack/Ozow routing, PEP branch validation and confirmation guards, owner exclusion, CSRF rejection, invalid methods, cart preservation and live-provider fail-closed behavior. Tests use disposable databases and create no live orders or notifications.

No Git or Render deployment command is included or executed.
