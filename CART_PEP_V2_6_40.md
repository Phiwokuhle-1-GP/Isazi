# Isazi V2.6.40 — local cart and PEP update

Apply to the existing V2.6.39 application. Stop Flask before installing. This patch does not commit, push or deploy.

Cart quantities update automatically using +, − or typed quantities. Remove refreshes the cart, totals and header badge. The server remains authoritative for stock, discounts and totals. Rapid changes are queued in order; an uncertain network response recovers by reading the cart rather than repeating a transaction. Without JavaScript, the existing Update and Remove forms remain available.

PEP branch suggestions start at three characters. Search matches town, suburb, branch name or code, ignores accents and shows up to eight suggestions from the supplied directory. The customer must select a branch. Keyboard arrows, Enter and Escape are supported, and the native branch dropdown remains available.

PEP delivery is fixed at R59.95 for every basket value: Standard Bag (45cm × 37cm), delivery in 7–9 business days. An unset or old owner fee no longer blocks checkout. Example: R450 goods + R59.95 delivery = R509.95. Courier remains fixed at R99; collection remains free. Existing historical order fees are preserved. PEP bank payment still requires owner confirmation.

Extract the ZIP, then run in PowerShell (replace TARGET with the existing app folder):

```powershell
python .\APPLY_CHECKOUT_PATCH.py --target "TARGET" --check
python .\APPLY_CHECKOUT_PATCH.py --target "TARGET"
```

The installer checks every changed file before writing and backs up changed code under `_update_backups`. It does not copy a database or uploads. It refuses unexpected local edits and can be safely rerun.

Start `START_WINDOWS.ps1` from TARGET, check `/health` reports 2.6.40 and refresh the browser with Ctrl+F5. Check cart quantities/removal, a three-letter branch search, branch selection and the R59.95 PEP total locally before any future deployment.

Validation: 152 Python application tests and six JavaScript interaction tests passed. JavaScript tests use development-only linkedom (`CART_TEST_DOM` points to its installed module); no application runtime dependency was added. No browser visual verification or live payment was performed.
