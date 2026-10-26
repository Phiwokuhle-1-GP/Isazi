# ISAZI AGILE STUDIO — ECS Client Project Manager

**A secure Isazi owner-entry application with a public under-construction website and an editable, four-page Flask Agile management system** for the Isazi Herbal Shop project, delivered by Executive Communication Services (ECS). Designed for a client meeting, ongoing requirements management, sprint delivery and an audit trail of every project-plan change.

> **Important:** This software manages the **project plan**. The public landing page is **not** a live shop or checkout. The owner dashboard includes clearly labelled planned modules, not a working customer shopping website, payment gateway, or sales-agent commission engine. Those are features planned for the separate Isazi e-commerce implementation.

## What is included

| Page | Functionality |
| --- | --- |
| **Public construction page** | Public homepage with Isazi branding, preview imagery and a protected Owner / ECS login link; visitors cannot access the project plan |
| **Owner login & home** | Password-hashed account created during first run, role-protected owner dashboard with development-status modules; change-own-password form |
| **1. Agile & Objectives** | Editable Agile introduction, principles, vision, plan overview, objectives; visual Plan → Build → Test → Review → Improve flow |
| **2. Scope & Stakeholders** | CRUD stakeholder roles, in-scope/out-of-scope features, solution architecture |
| **3. Sprint Roadmap** | Editable six-sprint roadmap, goals, owners, work items and live sprint statuses; milestones; story completion by sprint |
| **4. Backlog & Controls** | Editable user stories with acceptance criteria, owner, points, priority, sprint and status; a Kanban toggle; customer/agent/owner journeys, KPIs, risks and next actions |
| **Version history** | Immutable full-state snapshots for each save, change author/time/reason, checkpoint, compare unified diff, restore-as-new-version |
| **Accounts** | Admin / editor / viewer permissions, hashed credentials, session CSRF protection, manual account provisioning |
| **Export** | JSON backup of project plan, CSV export of stories, browser print (landscape A3-friendly CSS) |

## Quick start — Windows 11 (PowerShell)

1. Extract ZIP to a folder on your PC, e.g. `C:\Users\USER\Downloads\isazi_ecs_agile_manager`.
2. Double-click `RUN_WINDOWS.bat`, **or** open PowerShell in the folder and run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\START_WINDOWS.ps1
   ```

3. On first run, select an **owner password of at least 12 characters** and confirm it. Nothing will be sent to ECS or ChatGPT; the password is hashed locally.
4. Open <http://127.0.0.1:5000> in your browser and sign in with **owner** and your chosen password.
5. Edit items using **Edit** or **+ Add**; each save creates a new version in **History**.

First-time installation requires internet to download Python dependencies. Requires Python **3.10+**.

## Manual setup (Windows / macOS / Linux)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py init --username owner
python app.py serve
```

Navigate to <http://127.0.0.1:5000>. To stop, press Ctrl+C in the terminal.

## Editing workflow

- At `/` visitors see the **Under Construction** page; at `/login` authorised users sign in; at `/owner` only the admin-level owner can see the owner dashboard.
- Use **Security** → **Change password** to change your own password. No default passwords are packaged.
- Use the **4 navigation tabs** to move between the A3-style project sections.
- Click **Edit** to update an existing item, or **+ Add** to create a new one.
- Enter a meaningful **Change summary** (e.g. "Client approved sprint 2 product scope").
- Under **History**, click **Inspect**, **Compare** or **Restore as new version**.
- Updates use **optimistic concurrency**: an edit opened from an old version is refused rather than overwriting another user's changes.
- In the **Backlog** view, assign each story to a sprint and move its status through Backlog → Ready → In progress → In review → Done (or Blocked). Completion indicators on the roadmap update automatically.
- Under **Accounts**, an admin can create client viewers or ECS editors. Client viewers cannot modify content.
- Use **Print / A3 PDF** to print the current page; choose A3, landscape and print backgrounds in browser settings. The browser may paginate very long tables, rather than shrink text to illegibility.

## Version control — two complementary layers

1. **Business content:** SQLite `revisions` table saves the entire plan state on every change. Restoring v3 while on v8 produces **v9**, preserving all nine revisions. **History** supports full diff comparisons.
2. **Application code:** Initialise a Git repository in the extracted directory (`git init`, `git add .`, `git commit -m "Initial ECS Isazi Agile Studio"`). Git tracks code/templates/CSS; the SQLite DB and keys are ignored by `.gitignore`. Use GitHub only after your own repository and credentials are configured; this app does not automatically push to GitHub.

**Backups:** Download JSON from Export regularly. Also safely back up `instance/isazi.sqlite3` when the app is stopped. JSON export covers **plan data**, not user accounts or password hashes.

## Security and deployment guidance

- Local server binds to `127.0.0.1` by default. Do **not** expose Flask's development server publicly.
- For a real hosted client rollout, configure HTTPS, secrets in hosting environment variables, protected backups, a WSGI server (Waitress/Gunicorn), appropriate network restrictions, centralized logging and a privacy policy. Use `ISAZI_HTTPS=1` when fully behind HTTPS.
- Only administrators can invite new accounts. The session cookie is HTTP-only and SameSite=Lax; forms include CSRF tokens. Passwords use Werkzeug's salted password-hash functions.
- There is no public self-registration. The demo assumes ECS controls account onboarding.
- Medical-condition language and product claims must be checked before they appear in a public online shop. This plan intentionally does not present medical efficacy claims as fact.
- This sample uses SQLite, appropriate for a small internal project team; scale to PostgreSQL and production hosting after review.

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests verify seeding, every collection schema, edit snapshots, version conflict rejection, restore history, story CRUD, failed validation rollback and named checkpoints. A production release should also add browser-based end-to-end tests in its configured Flask environment.

## Files

- `app.py` — Flask routes, login, role guards, CSRF, editor, history, exports
- `state.py` — SQLite data model, seed user stories/sprints and revision engine
- `templates/page1.html` ... `page4.html` — all four editable project pages
- `templates/edit.html` — forms for updating project data
- `static/style.css` — responsive dark-green/white theme and A3 landscape print rules
- `static/img/reference_page_*.png` — original four infographic design references
- `tests/test_state.py` — self-contained state/version-control tests
- `START_WINDOWS.ps1` and `RUN_WINDOWS.bat` — Windows startup helper

**Draft status:** six-sprint / 12-week schedule is a planning assumption, not a final contractual commitment. Targets are **To agree**, not invented live performance data. All progress fields start as proposed/untested and must be updated by project users.

## Local admin account recovery

If the initial owner password is forgotten, stop the local server, open a trusted terminal in the project directory with the virtual environment active, and run:

```powershell
python app.py reset-password --username owner
```

Enter and confirm a new password. For security, avoid running this recovery command in an unattended or shared shell.

## Owner login details (set at first launch)

- **Local public landing page:** `http://127.0.0.1:5000/`
- **Owner login:** `http://127.0.0.1:5000/login`
- **Owner dashboard:** `http://127.0.0.1:5000/owner` (admin role only)
- **First-run username:** `owner` (unless `python app.py init --username <other>` was used)
- **Password:** chosen privately at initial setup. There is **no shipped password**.
- **Password reset:** stop the app and run `python app.py reset-password --username owner` from its virtual environment; it prompts for the new password without exposing it.
- **Existing installations:** accounts and history persist in the existing `instance/isazi.sqlite3`; an existing `admin` account continues to work. Back up this file before replacing an existing installation.

### Roadmap for a future live store

The new protected `/owner` area is the intended entry point for future catalogue, orders, checkout reconciliation, inventory, customer support and sales-agent modules. **These features are placeholders, not functional commerce services today.** A production e-commerce launch requires dedicated models, payment-provider onboarding, webhook validation, inventory transactions, privacy review, product compliance, HTTPS and operational testing.

Public artwork is stored at `static/img/owner_login_concept.png` (graphic preview only, not a live login form), with a cropped image used in the live construction page.

---

## Version 3 — Client progress tracker and website design catalogue

**This edition extends the owner portal without discarding earlier plans, users, snapshots or accounts.** Two client-facing pages are available after sign-in:

| URL | Purpose | Who may update |
| --- | --- | --- |
| `/client/progress` | Easy-to-read, nine-step delivery tracker: owner, target, required evidence, status, and comments | ECS admin/editor changes official statuses; signed-in client viewers can comment |
| `/client/designs` | Three website style proposals with browsable live HTML/CSS previews | Client viewers can open designs and leave preferences/change requests |
| `/client/designs/<id>` | Large individual design preview with desktop/mobile toggle, highlights and dated feedback | ECS admin/editor sets the formal design status |
| `/history` | Immutable saved plan revisions, including delivery status and catalogue changes | Editors can restore; viewers can inspect |
| `/export/client-feedback.csv` | Append-only comment history with author, type, subject and timestamp | Signed-in accounts may export |
| `/export/json` | Plan + full client-feedback data export | Signed-in accounts may export |

### First three project steps

1. **Domain registration:** Name/registrar, DNS ownership, confirmed registration evidence. Default **Not started**; no domain registration is claimed to have occurred.
2. **Design selection and finalisation:** Client reviews, selects an approach, and signs off the design. Default **Awaiting client**.
3. **Design catalogue and client review:** Three style variations available for review, notes and revision requests. Default **In review**. These statuses are initial *planning placeholders*, not verified completion reports.

Six additional steps cover product/content sign-off, storefront build, payment sandbox, owner/agent tooling, UAT, and production release.

### How the client uses it

1. ECS owner signs in and goes to **Accounts**. Create a **viewer** login for an authorised Isazi client representative, with a private random password (12+ characters).
2. The client signs in at `http://127.0.0.1:5000/login` from the same machine (or through a properly deployed, HTTPS-protected production service when later configured). Localhost is **not** remotely accessible to the client over the public internet.
3. Client opens **Client progress** for statuses and steps, or **Design catalogue** to review concepts.
4. Each concept can be viewed as **desktop** or **mobile** using the toggle. Select **Comment**, **Prefer this design**, or **Request changes**, then write the reason and save.
5. ECS reviews feedback and updates the official design state to `Selected`, `Approved`, or `Changes requested`. Client comments **never automatically approve** a design.
6. ECS updates progress statuses using the inline controls and writes an appropriate reason for plan edits. All formal changes appear in version history; notes remain timestamped/append-only in the separate feedback audit table.

### Design variations (real HTML/CSS prototypes)

- **Botanical Classic:** traditional green and cream, clear categories and product cards.
- **Premium Earth:** forest green, warm gold/cream, more editorial presentation.
- **Clean Modern:** minimal shopping-first layout with prominent search and compact cards.

The visual prototypes use cropped photographs from the client-supplied product catalogue solely as concept assets. The displayed buttons do not take orders or accept payments. Product information and health claims must undergo client and regulatory review before a storefront is published.

### Upgrading from Version 2 without losing client data

1. **Stop the app**; make a secure, private backup of the entire prior `instance/` directory, including `.secret-key` and `isazi.sqlite3`.
2. Extract the v3 ZIP and copy files over your existing project folder, **leaving the original `instance/` contents intact**. Do not replace your `instance/` directory with a blank one.
3. Start `RUN_WINDOWS.bat`, then sign in with the existing `owner` or `admin` account.
4. On first launch, an idempotent schema migration adds the client-feedback table and the new `client_steps` and `designs` collections. **If the plan already exists, a new numbered revision documents this migration.** All original revision snapshots remain available. If an older revision without these two collections is restored, the new collections remain in the active plan.
5. Open `/client/progress` and `/client/designs` and review starter statuses and concepts with the client.

This update **does not** register domains, configure DNS, send emails, deploy a live site or process payments. Those require separate implementation and client approval.

### Security and backup notes

- All progress and design pages require authentication. The public construction homepage is unchanged.
- Only admin/editor users can set formal step and design status. A viewer can submit append-only feedback but cannot edit plans, statuses or user accounts.
- The user is stamped automatically on every comment. CSRF protection is required for all updates. The site has no public self-registration.
- Back up the SQLite database along with project assets; a JSON export contains the plan and notes, but **not credentials**.
- Local Flask development mode is not suitable for public client access. For hosted use, set up HTTPS and production security, and verify POPIA obligations.
- When modifying the code, keep it under Git source control; content revisions are tracked independently in SQLite.
