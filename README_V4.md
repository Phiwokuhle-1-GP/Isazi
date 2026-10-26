# Isazi Herbal Shop — ECS Agile Owner Portal v4

This project extends the tested v3.1 Flask project manager, retaining all previous owner/admin functions and project plan version history.

## Client-facing experience

The owner can create a `viewer` account in **Accounts**. When the client signs in, they land on the simplified **Client progress** page instead of the internal Agile documentation. They can see completed steps, steps awaiting feedback, planned steps, dates, responsibilities, comments, and the design-selection stage. ECS editors/admins can change official statuses, which are snapshot-versioned.

The **Download status report (PDF)** control creates a report dynamically from the SQLite database. It reports the current project version, steps/statuses, items awaiting client review, design status and latest recorded feedback. The PDF route is authenticated; a PDF download does not create a new revision.

### Website design catalogue

Three full-page storefront prototypes are provided and are browseable on desktop/mobile:

- Botanical Classic: natural green-and-white, traditional, friendly.
- Premium Earth: muted green, warm neutrals, editorial presentation.
- Clean Modern: search- and shopping-led, minimal layout.

The prototypes have working sample navigation anchors, category filters, four item cards, quick view and a simulated cart. **They do not create orders, accounts, payments or inventory changes.** Individual prices are based on the original user-supplied catalogue and need owner approval.

The preview route permits same-origin iframe embedding for the client design review. Other application routes retain `X-Frame-Options: DENY` and restrictive CSP. Authentication protects all client details.

## Installation on existing v3.1

Run `INSTALL_V4_WINDOWS.ps1` after extracting the release ZIP. It safely backs up the current `instance` database/secret and project source before overwriting application files. Run `python -m pip install -r requirements.txt` inside your `.venv` to add ReportLab. Restart Flask. Your existing owner credentials remain.

## Test coverage

Unit tests for the database, revision engine and PDF report are located in `tests/`. Flask routes require an environment with Flask installed; these could not be exercised in this output environment. To test locally:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Other important limitations: this is a private project manager and website prototype, not a payment-enabled e-commerce shop. Use HTTPS, a production WSGI server, secure cookie config and security review before giving remote access.
