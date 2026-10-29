# Isazi V2.6.4 — Client demonstration

## Start the presentation

Stop the old server with Ctrl+C, apply the V2.6.4 update, then run the demo launcher from your existing installation:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\Downloads\Isazi_Flask_Store\Isazi_Herbal_Shop_V2\START_DEMO_WINDOWS.ps1"
```

Open http://127.0.0.1:5000/ and press Ctrl+F5. The gold bar says CLIENT DEMO. At `/health`, `version` is `2.6.4` and `demo_mode` is `true`. If that flag is false, stop the process and use START_DEMO_WINDOWS.ps1.

The launcher starts a separate `instance-client-demo/` store and a separate browser session cookie. It ignores the normal DATA_DIR setting while selecting its demo folder. It never resets the normal database or changes real product stock. The six active sample products start with 50 units each in the demo database. Demo orders reserve that demo stock normally. Subsequent starts preserve demo orders and remaining quantities rather than replenishing stock automatically.

No owner credential is created or changed. The normal owner account is still in the normal store. Do not run CREATE_OWNER to update an existing owner. The demo uses packaged default assets; custom media uploaded to your normal installation is not copied into it.

## Suggested client walkthrough

1. **Shop:** click Shop in the white navigation. All active demo products appear. Search, filter or sort the full catalogue.
2. **Product:** open a product; show the description/tabs and quantity buttons. Back to Shop and Continue shopping return to `/shop`.
3. **Cart:** choose Add to Cart. The item is added and the cart opens. Change its quantity and click Update, remove it, or continue shopping. The header cart count updates after the server saves the change.
4. **Customer account:** adding the first item prepares a private sample account with sample contact details. The account icon opens My Account. You can also open a sample account before shopping using its one-click form. Each fresh browser session gets its own sample customer; there is no shared customer password or owner login bypass.
5. **Checkout:** your sample name/email/phone are filled in. Choose collection or Randburg delivery; a saved demo address can populate the delivery address. Tick the consent checkbox, then Continue to Demo Payment.
6. **Payment selection:** choose Visa, Mastercard, Yoco, Ozow, PayFast or EFT. Each opens an internal preview with your sample order total. The card illustration is sample information; no real card or bank details are requested.
7. **Payment result:** click Simulate Successful Payment. The receipt displays the demo order and a recorded demo payment. My Account & Orders returns to the same customer's order history. Repeating this action does not add a second receipt or reserve stock again.
8. **Account:** show My Orders, view a receipt, edit details, save addresses and save a product from its detail page. For the password/registration journey, create a separate sample account with a password you choose; the one-click account has an unknown random password and is intended for the order/account demonstration.
9. **Alternative paths:** Cancel payment / View order leaves the sample order awaiting payment. You can return later to choose a demo method. A cancelled order cannot be marked paid through the simulator.

The journey links connect Shop, Cart, Checkout, Payment and My Account. Provider tiles in the cart also open preview pages before an order is placed. In normal store mode, these provider preview links stay read-only; actual PayFast checkout continues to use its existing separately configured order payment route.

## What is simulated

No payment provider, bank or email server is contacted by demo checkout. Demo mode forces live PayFast and SMTP configuration off, even if merchant/email environment variables are present. Successful demo payment writes a receipt labelled `CLIENT DEMO / <method>` in the isolated demo database and updates the demo order to Paid. It does not charge, refund or transfer money. GET previews cannot mark orders paid; the explicit CSRF-protected simulation action does that.

Payment previews are internal presentation screens, not actual Yoco/Ozow/Visa/Mastercard merchant connections. No merchant account was created or configured. Real PayFast still requires your merchant credentials, HTTPS hosting and an end-to-end sandbox test outside this demo mode.

The four audio-testimony covers and poolside story placeholder remain. Actual audio/video files must be uploaded separately; no recordings are invented. The hero blending/colour refinement and aligned Listen to testimonials section are included.

## Return to the normal store

Stop the demo with Ctrl+C. Start `START_WINDOWS.ps1` to return to normal store operation. The normal store's existing data, owner login, uploads and stock are retained. Products with unconfirmed/zero real stock still respect the normal availability checks. For the 29 October main-store presentation, START_WINDOWS.ps1 also enables payment tests while retaining the normal database and accounts. Use START_WINDOWS.ps1 -LivePayments to disable main-store simulated completion; the standalone demo remains separate. Owner sessions cannot sign in/register as customers until owner sign-out.

Do not use the demo launcher to take real orders. Demo pages are marked noindex/nofollow and no-store. The app is still bound to local host by app.py. A public deployment and real payment/email/courier connectivity have not been performed for this presentation.

## Validation

Automated checks cover the full product → cart → checkout → each payment preview → simulated receipt → My Orders journey, separate stock/databases/cookies, private sample accounts, payment replay protection, cancelled orders, CSRF checks and disabled live integrations. Windows PowerShell was reviewed but could not be run in this Linux environment. Browser layout checks use Flask-rendered HTML; backend flows are exercised with Flask's test client.

## Reset an owner password privately

Stop the app before resetting. In the installed project folder, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\RESET_OWNER_WINDOWS.ps1 -ClientDemo
```

Enter the new password twice when prompted (16 characters minimum). This creates or replaces only the demo owner password. Restart START_DEMO_WINDOWS.ps1, then use /owner/login. To reset the normal store owner instead, omit -ClientDemo and restart START_WINDOWS.ps1. Products, orders, uploads and customer passwords are not reset. No password is embedded in the package or written in chat.
