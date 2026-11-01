# V2.6.39 — direct cart payment selection and fixed R99 courier

Local follow-up patch for an app already updated to V2.6.38. No Git commit, push, merge or Render deployment was performed.

## Behavior

- The cart payment cards now submit the selected option directly. Signed-out customers go to cellphone registration/sign-in; signed-in customers go directly to delivery/order details. Selecting a payment card does not open another method-selection screen.
- The delivery option is labelled **Courier delivery — fixed R99**. New courier orders cost R99 regardless of basket value or discounts. Free collection remains available. PEP pickup keeps its separate configured fee and existing workflow.
- Totals in JavaScript and on the server use R99. The server ignores posted shipping amounts, requires a full courier address and calculates the final payable amount itself.
- The header, cart delivery note and delivery-policy wording now match the courier rule. The business location remains Randburg, Johannesburg; only delivery-region restrictions and obsolete pricing are removed.
- Existing order totals are preserved. Legacy `randburg` order values still display as Courier delivery and remain readable. New courier orders use `courier`.
- A one-time startup update replaces the stored delivery-note setting with the new courier/collection/PEP wording. Other owner settings, accounts, products, stock, uploaded media and payment configuration are retained.
- Paystack and Ozow remain test journeys until real adapters are implemented. In live-payment configuration the unconnected options remain disabled and rejected by the server.

## Local installation

Stop Flask with Ctrl+C. Extract the ZIP into Downloads, then run:

```powershell
$patch = "$HOME\Downloads\Isazi_Checkout_V2_6_39"
$target = "$HOME\Downloads\Isazi_Git_2634_retry_20261031_114226"
python "$patch\APPLY_CHECKOUT_PATCH.py" --target "$target" --check
python "$patch\APPLY_CHECKOUT_PATCH.py" --target "$target"
cd "$target"
powershell -ExecutionPolicy Bypass -File .\START_WINDOWS.ps1
```

Use the same target folder where V2.6.38 was installed. The installer refuses unexpected file contents, creates timestamped code backups, and does not copy or replace the database. On startup only the new delivery-note setting is migrated. Verify `/health` reports 2.6.39 and hard-refresh with Ctrl+F5.

## Review

Reviewable unified changes are supplied in `checkout.patch`. Tests cover direct cart selection, returning-customer behavior, courier address validation, R99 below and above R600, posted-total tampering, free collection and preserved PEP behavior. The regression suite also covers payment isolation, stock and owner operations. Manual browser checks remain recommended for desktop and mobile.

Nothing in this package commits, pushes or deploys code.

Validation result: all 147 regression tests passed. JavaScript syntax checks passed. Installer dry-run, V2.6.38 upgrade, idempotent reapply, startup delivery-note migration, database preservation and historical delivery-charge preservation passed.
