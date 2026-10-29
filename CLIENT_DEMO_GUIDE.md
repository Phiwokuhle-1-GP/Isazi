# V2.6.6 unified dry run

Use START_WINDOWS.ps1 for one shared store. START_DEMO_WINDOWS.ps1 is now an alias to it. Do not switch databases to demonstrate checkout.

1. Open /health: version 2.6.6, demo_mode false, demo_payments_enabled true.
2. Open /owner/login in your normal browser profile. Test stock defaults to 50 per product and is editable in the product form. Real stock is separate.
3. Open another browser profile/incognito window as a customer. Register at /account/register. Browse Shop, open a product and Add to Cart.
4. Update quantities, check out, select Visa/Mastercard/Yoco/Ozow/PayFast/EFT and simulate successful payment. No money moves. Receipt and My Orders persist.
5. Return to the owner profile. Recent orders shows the same order with Test payment; open it to see the payment, customer, address and quantities. Mark Ready or Completed, or cancel to restore test stock once.
6. The owner dashboard has Saved test orders and Simulated receipts. Reports → Test orders / dry run includes them; Real orders excludes them. Restart the store and verify the order is still there.

Owners cannot purchase or sign in as customers in their current session. Sign out before switching roles, or keep different browser profiles. No shared sample customer/password is used.

New test orders consume presentation stock only. Existing older test orders retain their original inventory pool so cancellation remains correct. No data is reset on update/restart. Test recordings must be uploaded separately in Media & Testimonials.

Disable simulation after the dry run with START_WINDOWS.ps1 -LivePayments, or DEMO_PAYMENTS_ENABLED=0 on Render. This requires a manual restart; no automatic expiry occurs. Test orders and test reports remain saved. Real provider credentials and verification are separate work.
