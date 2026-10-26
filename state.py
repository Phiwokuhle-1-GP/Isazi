"""SQLite persistence, validations and immutable snapshot version control.

Can be tested without Flask installed.
"""
from __future__ import annotations

import datetime as dt
from contextlib import contextmanager
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

SCHEMA = {
    "client_steps": (3, [("title", "Delivery step", "text"), ("detail", "Description & acceptance criteria", "textarea"), ("status", "Current status", "client_status"), ("owner", "Responsible party", "text"), ("target", "Target or due date (TBC if unknown)", "text"), ("evidence", "Evidence / decision needed", "textarea")]),
    "designs": (2, [("title", "Design variation name", "text"), ("description", "Style and intended audience", "textarea"), ("theme", "Visual layout", "design_theme"), ("status", "Design status", "design_status"), ("features", "Design highlights (one per line)", "textarea")]),
    "principles": (1, [("title", "Short principle", "text"), ("detail", "What it means", "textarea")]),
    "objectives": (1, [("title", "Objective", "text"), ("detail", "Success description", "textarea")]),
    "stakeholders": (2, [("title", "Stakeholder / role", "text"), ("responsibilities", "Responsibilities (one per line)", "textarea")]),
    "scope_in": (2, [("title", "Included feature", "text"), ("detail", "Scope notes", "textarea")]),
    "scope_out": (2, [("title", "Excluded feature", "text"), ("detail", "Scope notes", "textarea")]),
    "systems": (2, [("title", "System component", "text"), ("detail", "Purpose / integration", "textarea")]),
    "sprints": (3, [("title", "Sprint title", "text"), ("weeks", "Weeks", "text"), ("goal", "Sprint goal", "textarea"), ("tasks", "Planned tasks (one per line)", "textarea"), ("status", "Status", "sprint_status"), ("owner", "Owner", "text")]),
    "milestones": (3, [("title", "Milestone", "text"), ("due", "Target date or week", "text"), ("deliverable", "Evidence of completion", "textarea"), ("status", "Status", "status")]),
    "stories": (4, [("title", "User story / feature", "text"), ("persona", "As a...", "persona"), ("want", "I want to...", "textarea"), ("benefit", "So that...", "textarea"), ("acceptance", "Acceptance criteria", "textarea"), ("priority", "Priority", "priority"), ("status", "Status", "story_status"), ("sprint", "Sprint", "sprint"), ("points", "Story points", "points"), ("owner", "Assigned to", "text")]),
    "journeys": (4, [("title", "Journey name", "text"), ("persona", "Customer / agent / owner", "persona"), ("steps", "Journey steps (one per line)", "textarea")]),
    "kpis": (4, [("title", "KPI", "text"), ("target", "Target", "text"), ("actual", "Actual", "text"), ("unit", "Unit / measurement notes", "text")]),
    "risks": (4, [("title", "Risk", "text"), ("impact", "Business impact", "textarea"), ("mitigation", "Mitigation strategy", "textarea"), ("likelihood", "Likelihood", "likelihood"), ("status", "Status", "risk_status"), ("owner", "Risk owner", "text")]),
    "next_steps": (4, [("title", "Next action", "text"), ("detail", "Details", "textarea"), ("status", "Status", "status")]),
}

CHOICES = {
    "client_status": ["Not started", "In progress", "Awaiting client", "In review", "Approved", "Completed", "Blocked", "On hold"],
    "design_status": ["Proposed", "Under review", "Changes requested", "Selected", "Approved", "Archived"],
    "design_theme": ["botanical", "premium", "modern"],
    "priority": ["High", "Medium", "Low"],
    "status": ["Not started", "In progress", "Completed", "On hold"],
    "story_status": ["Backlog", "Ready", "In progress", "In review", "Done", "Blocked"],
    "sprint_status": ["Planned", "Active", "Review", "Completed"],
    "risk_status": ["Open", "Mitigating", "Closed"],
    "likelihood": ["Low", "Medium", "High"],
    "persona": ["Customer", "Sales agent", "Owner / Admin", "Bulk buyer", "Other"],
    "sprint": ["Backlog", "Sprint 1", "Sprint 2", "Sprint 3", "Sprint 4", "Sprint 5", "Sprint 6"],
    "points": ["0", "1", "2", "3", "5", "8", "13", "21"],
}

# Baseline features are subject to written client confirmation.
# Commercial amounts and invoicing are handled separately by ECS.
COMMERCIAL_SCOPE_FIELDS = {
    "included": "Included in the agreed scope (one item per line)",
    "excluded": "Not included / available through a separate quotation (one item per line)",
    "third_party": "External / recurring charges payable separately (one item per line)",
    "client_duties": "Client information and approvals required (one item per line)",
    "change_control": "Extra-services approval process",
    "tax_note": "VAT and payment terms clarification",
    "scope_status": "Scope confirmation state",
    "signoff_reference": "Written scope approval evidence/reference (if available)",
}
SCOPE_STATUS = ("Draft for confirmation", "Client review", "Approved in writing")

def default_commercial_scope():
    return {
      "scope_status": "Draft for confirmation",
      "signoff_reference": "",
      "included": "\n".join([
        "One responsive Isazi Herbal Shop website using one selected and approved homepage design concept.",
        "Core pages: home, shop catalogue, product details, cart/checkout, about and contact; standard store-policy page templates for client review.",
        "Initial product catalogue setup using the supplied and client-approved product list, photos, descriptions and prices.",
        "Shopping cart, customer account/login and basic order status tracking.",
        "Technical integration of one South African payment gateway (PayFast or Yoco), subject to provider approval and successful testing.",
        "Basic secure owner dashboard for products, customer orders, stock levels and order status updates.",
        "Basic sales-agent portal for agent registration/approval, referral codes and commission recording under client-approved rules.",
        "Basic sales, order and agent performance reporting from real store records.",
        "Mobile-responsive styling, essential on-page SEO metadata, functional testing and agreed production deployment assistance.",
        "Initial owner handover, usage guidance and agreed acceptance fixes before launch.",
      ]),
      "excluded": "\n".join([
        "Additional website design concepts implemented as separate live websites, or a major redesign after final design approval.",
        "Native Android or iOS app, marketplace build, ERP/POS/accounting integration or international/multi-currency commerce.",
        "Advanced automations, AI recommendations, custom courier connections, bulk data migration or specialist integrations.",
        "Paid advertising, ongoing SEO/content campaigns, social media management and professional photography or copywriting.",
        "New product uploads or content changes beyond the agreed initial catalogue and acceptance scope.",
        "Extended training, ongoing maintenance, support retainers and feature changes requested after sign-off/handover.",
        "Medical, regulatory or legal certification and validation of health-related product claims.",
      ]),
      "third_party": "\n".join([
        "Domain name registration and annual renewal fees (ECS can coordinate registration).",
        "Web hosting, platform/database hosting, SSL products if paid, business email and renewal charges.",
        "Payment gateway transaction, settlement or onboarding fees set by the provider.",
        "Courier/shipping fees, packaging, SMS/WhatsApp API usage and paid plugins or external subscriptions.",
      ]),
      "client_duties": "\n".join([
        "Confirm domain ownership and provide/authorise registrar and payment-provider accounts.",
        "Supply final product names, price list, stock, images, labels, ingredients and approved descriptions.",
        "Review design selection and approve the chosen concept and consolidated changes in writing.",
        "Supply and approve shipping/returns/privacy policies, commission rules and required notices.",
        "Arrange any required product/regulatory approvals and review medical claims before publication.",
        "Provide timely acceptance feedback, test accounts and go-live approval.",
      ]),
      "change_control": "Any work not explicitly included in the approved scope is a separately charged service. ECS will describe the extra service, cost and effect on the timeline in a separate written quotation. ECS will not start chargeable additional work until Isazi accepts that quotation in writing. A client comment, design preference or status update alone is not approval for extra charges. Any changes to the agreed scope must be approved in writing by both parties.",
      "tax_note": "Commercial terms, VAT, payment milestones and invoicing are managed separately by ECS through the signed quotation or agreement. This portal records scope and progress only, and is not an invoice.",
    }



def sanitize_commercial_scope(scope: dict) -> bool:
    """Remove the legacy project amount from the active scope, not historical revisions.

    Any future billing remains outside this planning portal, with ECS.
    """
    import re
    changed = bool(scope.pop("price_zar", None) is not None)
    defaults = default_commercial_scope()
    replacement = "agreed scope"
    for key in ("included", "excluded", "third_party", "client_duties", "change_control", "tax_note"):
        value = scope.get(key)
        if not isinstance(value, str):
            continue
        original = value
        if key == 'change_control' and re.search(r'R\s*5[,. ]?999', value, re.I):
            value = defaults['change_control']
        elif key == 'tax_note' and re.search(r'R\s*5[,. ]?999', value, re.I):
            value = defaults['tax_note']
        else:
            value = re.sub(r'R\s*5[,. ]?999(?:\.00)?', replacement, value, flags=re.I)
        if value != original:
            scope[key] = value
            changed = True
    return changed

OVERVIEW_FIELDS = {
    "project_name": "Project name", "client": "Client", "delivery_partner": "Delivery partner",
    "summary": "Project overview", "agile_intro": "Introduction to Agile",
    "agile_cycle": "Delivery approach", "vision": "Business vision", "assumptions": "Assumptions / approvals needed",
}


def item(**kwargs):
    return {"id": str(uuid.uuid4()), **kwargs}


def seed_state() -> dict:
    stories_raw = [
        ("Browse herbal products", "Customer", "explore and search a clear product catalogue", "I can compare products and make informed choices", "Product pages show accurate prices, images, ingredients and appropriate product information.", "High", "Sprint 2", "3"),
        ("Add products to cart", "Customer", "add items and update quantities", "I can prepare my order", "Cart totals recalculate correctly and stock is checked.", "High", "Sprint 2", "3"),
        ("Pay securely", "Customer", "check out using a trusted payment provider", "I can complete my purchase safely", "Successful payments are verified using server-side provider callbacks; failed payments do not mark orders paid.", "High", "Sprint 3", "8"),
        ("Create customer account", "Customer", "register and sign in", "I can view my orders", "Password protection, basic account recovery and access controls work.", "High", "Sprint 3", "5"),
        ("Track my order", "Customer", "view my order status", "I know what happens next", "Order history and delivery statuses are visible to the purchaser.", "High", "Sprint 3", "5"),
        ("Manage products", "Owner / Admin", "create, edit and archive products", "my catalogue stays accurate", "Only authorised team members can update catalogue details.", "High", "Sprint 4", "5"),
        ("Manage customer orders", "Owner / Admin", "update fulfilment status", "orders are handled efficiently", "Status transitions are recorded and visible to authorised users.", "High", "Sprint 4", "5"),
        ("Manage inventory", "Owner / Admin", "record stock and low-stock levels", "we can prevent avoidable stockouts", "Stock levels and alerts reflect completed and cancelled orders.", "High", "Sprint 5", "5"),
        ("Register as a sales agent", "Sales agent", "apply and get a unique referral code after approval", "I can refer shoppers", "New agents require approval; unique codes are generated once.", "High", "Sprint 4", "5"),
        ("Track referral commissions", "Sales agent", "view qualifying sales and earned commissions", "I can understand my earnings", "Refunds and cancelled orders reverse pending commissions; payouts require approval.", "High", "Sprint 4", "8"),
        ("View sales and KPI dashboard", "Owner / Admin", "see orders, revenue, stock and agent performance", "I can make better business decisions", "Reports reflect real data and show date filters.", "Medium", "Sprint 5", "5"),
        ("Receive order notifications", "Customer", "receive transaction and dispatch updates", "I am informed about my purchase", "Notifications include order reference without exposing payment data.", "Medium", "Sprint 3", "3"),
        ("Use the shop on mobile", "Customer", "browse and check out on my phone", "I can shop from any device", "Layout and forms are usable at 360px and above.", "High", "Sprint 2", "5"),
        ("Manage information pages", "Owner / Admin", "update store content and product warnings", "the shop stays accurate and compliant", "Changes are access-controlled and published content can be reviewed.", "Medium", "Sprint 5", "3"),
    ]
    return {
        "overview": {
            "project_name": "Isazi Herbal Shop — Digital Commerce Platform",
            "client": "Isazi Herbal Shop",
            "delivery_partner": "Executive Communication Services (ECS)",
            "summary": "Agile delivery of a mobile-friendly e-commerce storefront, customer accounts, sales-agent portal, owner dashboard, inventory and analytics. This plan is a client discussion draft, not an approved contract.",
            "agile_intro": "Agile is an iterative approach that delivers working software in short cycles. ECS prioritises valuable features, demonstrates progress, gathers feedback and adapts the plan with Isazi throughout delivery.",
            "agile_cycle": "PLAN → BUILD → TEST → REVIEW → IMPROVE. A proposed sprint lasts two weeks, with a review and backlog refinement at the end of each cycle.",
            "vision": "Make traditional herbal wellness products accessible through a trustworthy, convenient digital shop, subject to verified product information and applicable regulation.",
            "assumptions": "Proposed 6 sprints / 12 weeks, subject to agreed scope, product content, payment provider approval, compliance review, hosting and client sign-off. No payment or live shop is implemented by this planning tool.",
        },
        "commercial_scope": default_commercial_scope(),
        "client_steps": [item(title=t, detail=d, status=st, owner=o, target="To confirm", evidence=e) for t,d,st,o,e in [
            ("Domain registration", "Confirm the preferred .co.za name, registrar account ownership, DNS management and registration evidence.", "Not started", "Isazi / ECS", "Domain registration confirmation, DNS ownership details"),
            ("Design selection and finalisation", "Review website concepts, select a preferred visual direction and approve the final homepage, product and mobile designs.", "Awaiting client", "Isazi", "Written design approval and consolidated feedback"),
            ("Design catalogue and client feedback", "Browse different working visual concepts and record comments and requested changes against each proposal.", "In review", "Isazi / ECS", "Client comments, preferred concept, requested revisions"),
            ("Product catalogue and content sign-off", "Confirm names, pricing, photography, descriptions, labelling and compliance review before publication.", "Not started", "Isazi", "Approved product inventory and compliant descriptions"),
            ("E-commerce storefront build", "Implement responsive homepage, browsing, product details and cart with regular ECS demonstrations.", "Not started", "ECS", "Demonstrated working storefront and mobile acceptance checklist"),
            ("Payment gateway setup and sandbox", "Arrange merchant onboarding, payment-provider test account, checkout verification and payment reconciliation.", "Not started", "Isazi / ECS", "Verified test transactions and merchant approval"),
            ("Owner dashboard and sales-agent tools", "Implement authorised product/order administration and agreed agent attribution and commission features.", "Not started", "ECS", "Admin and agent user acceptance tests"),
            ("Testing and client acceptance", "Complete functional, accessibility, security and customer journey tests; record client issues and approvals.", "Not started", "Isazi / ECS", "Signed UAT checklist and issue resolution"),
            ("Production release and handover", "Final go/no-go, production DNS, backup, monitoring, training and agreed support arrangements.", "Not started", "Isazi / ECS", "Signed go-live approval and handover pack"),
        ]],
        "designs": [item(title=t, description=d, theme=th, status="Proposed", features=ft) for t,d,th,ft in [
            ("Botanical Classic", "Fresh herbal identity using leafy greens, clear product cards and approachable typography.", "botanical", "Prominent product photography\nQuick category browsing\nGreen shopping actions\nBright mobile-friendly layout"),
            ("Premium Earth", "Refined forest green, warm cream and gold details for a premium heritage-led wellness presentation.", "premium", "Elegant editorial hero\nPremium product presentation\nWarm neutral surfaces\nBrand storytelling first"),
            ("Clean Modern", "Minimal, airy commerce experience with large search, compact cards and quick browsing.", "modern", "Easy mobile navigation\nSearch-led product discovery\nHigh-contrast checkout actions\nSimple product comparisons"),
        ]],
        "principles": [item(title=t, detail=d) for t,d in [
            ("Customer value first", "Prioritise useful outcomes for shoppers and the owner."),
            ("Short iterations", "Deliver demonstrable work in approximately two-week sprints."),
            ("Collaborative feedback", "Review progress with client stakeholders regularly."),
            ("Adapt to change", "Reprioritise the backlog with documented decisions."),
            ("Working software", "Agree on demonstrable acceptance criteria for each feature."),
            ("Continuous improvement", "Use sprint retrospectives to improve delivery."),
        ]],
        "objectives": [item(title=t, detail=d) for t,d in [
            ("Customer storefront", "Mobile-friendly browsing, catalogue, cart and checkout."),
            ("Secure payments", "Integrate one approved South African payment gateway."),
            ("Owner dashboard", "Manage products, orders, stock and customer accounts."),
            ("Sales-agent portal", "Agent approval, codes, attributed sales and commission tracking."),
            ("Analytics", "Orders, revenue, fulfilment and agent performance reporting."),
            ("Growth-ready delivery", "Document, test, train and hand over a maintainable solution."),
        ]],
        "stakeholders": [item(title=t, responsibilities=r) for t,r in [
            ("Isazi Herbal Shop (client)", "Confirm products, prices, legitimate claims and business requirements\nReview demos and approve deliverables\nPrioritise backlog and decide policies"),
            ("ECS (delivery partner)", "Facilitate planning and sprint reviews\nDesign, implement and test agreed features\nManage technical risks and release quality\nTrain users and hand over documentation"),
            ("Customers and sales agents", "Test product browsing and checkout journeys\nProvide usability feedback\nReport issues during acceptance testing"),
            ("Third-party services", "Payment gateway onboarding\nHosting/domain/email configuration\nCourier or messaging integrations if approved"),
        ]],
        "scope_in": [item(title=t, detail=d) for t,d in [
            ("E-commerce storefront", "Product listings, product details, cart and responsive pages."),
            ("Customer checkout and accounts", "Approved provider integration and order history."),
            ("Owner administration", "Products, order states, customer management and stock."),
            ("Sales-agent portal", "Approvals, referral codes, commissions and tracking."),
            ("Sales reporting", "KPIs and operational reports from actual records."),
            ("Deployment and training", "Testing, release support and initial user guidance."),
        ]],
        "scope_out": [item(title=t, detail=d) for t,d in [
            ("Native mobile application", "A separate Android/iOS app would be a future phase."),
            ("ERP/accounting integration", "ERP integration needs separate discovery and estimate."),
            ("Physical store and POS", "Hardware, retail fit-out and point-of-sale not included."),
            ("Advanced AI recommendations", "Not required for the initial launch."),
            ("International checkout", "Multi-currency and cross-border tax/shipping in later scope."),
        ]],
        "systems": [item(title=t, detail=d) for t,d in [
            ("Customer Storefront", "Browse → product details → cart → pay → track order."),
            ("Payment Gateway", "Hosted/approved payment provider, server-side verification, refunds policy."),
            ("Owner Dashboard", "Products, customers, orders, stock and reports."),
            ("Sales Agent Portal", "Approved agents, unique codes, attributed sales and commission ledger."),
            ("Database & Analytics", "Persistent product/order records with role-based access."),
            ("Notifications & Delivery", "Email/WhatsApp updates and courier workflows as agreed."),
        ]],
        "sprints": [item(title=t, weeks=w, goal=g, tasks=tasks, status="Planned", owner="ECS") for t,w,g,tasks in [
            ("Sprint 1 — Discovery & Design", "Weeks 1–2", "Confirm requirements and approve the visual direction.", "Requirements workshops\nCustomer journeys and UX/UI mockups\nDatabase architecture\nProduct/compliance review checklist\nDevelopment setup"),
            ("Sprint 2 — Storefront", "Weeks 3–4", "Demonstrate product browsing and cart flow.", "Homepage and catalogue\nProduct detail pages\nCart prototype\nResponsive mobile layouts\nClient walkthrough"),
            ("Sprint 3 — Checkout & Customers", "Weeks 5–6", "Enable tested checkout in a sandbox.", "Payment provider sandbox\nCustomer registration and login\nOrder tracking\nConfirmation emails\nPayment callback tests"),
            ("Sprint 4 — Owner & Agent Portals", "Weeks 7–8", "Deliver role-specific management workflows.", "Agent registration and approval\nReferral codes and commission rules\nOwner product and order management\nBasic inventory controls"),
            ("Sprint 5 — Reporting & Hardening", "Weeks 9–10", "Deliver business reports and improve quality.", "Sales and order reports\nAgent performance dashboard\nInventory alerts\nSecurity and performance review\nClient acceptance rehearsal"),
            ("Sprint 6 — Launch & Handover", "Weeks 11–12", "Complete UAT, release and train stakeholders.", "End-to-end testing\nFix acceptance defects\nTraining and handover\nProduction deployment (after approval)\nSupport transition"),
        ]],
        "milestones": [item(title=t, due=w, deliverable=d, status="Not started") for t,w,d in [
            ("Project kickoff", "Week 1", "Approved scope and sprint 1 backlog"),
            ("Design signed off", "End Week 2", "Agreed visual design and flows"),
            ("Storefront demonstration", "End Week 4", "Browse/catalogue/cart reviewed"),
            ("Checkout UAT", "End Week 6", "Verified gateway sandbox and customer orders"),
            ("Agent and owner UAT", "End Week 8", "Management flows reviewed"),
            ("Go / no-go approval", "End Week 12", "Launch checklist and client sign-off"),
        ]],
        "stories": [item(title=t, persona=p, want=w, benefit=b, acceptance=a, priority=pr, status="Backlog", sprint=s, points=pt, owner="Unassigned") for t,p,w,b,a,pr,s,pt in stories_raw],
        "journeys": [item(title=t, persona=p, steps=s) for t,p,s in [
            ("Online shopper", "Customer", "Discover shop via search/social referral\nBrowse product information and prices\nAdd products to basket\nPay using secure hosted checkout\nReceive confirmation and track order\nReorder if satisfied"),
            ("Sales agent", "Sales agent", "Apply and await approval\nReceive unique code and permitted marketing guidance\nShare referral link responsibly\nCustomer checks out with attribution\nTrack qualifying commissions\nRequest approved payout"),
            ("Store owner", "Owner / Admin", "Log in to admin dashboard\nUpdate catalogue and stock\nReview orders and fulfilment\nApprove agents and commissions\nReview sales and operational KPIs\nAdjust priorities and business processes"),
            ("Bulk buyer", "Bulk buyer", "Review product and eligibility information\nRequest bulk quote\nConfirm availability and terms\nApprove and pay invoice\nReceive goods and documentation\nPlace repeat orders"),
        ]],
        "kpis": [item(title=t, target="To agree", actual="Not yet measured", unit=d) for t,d in [
            ("Monthly paid orders", "Orders/month, excluding cancelled/refunded orders"),
            ("Net sales revenue", "ZAR/month, less refunds and discounts"),
            ("Active sales agents", "Approved agents with qualified activity"),
            ("Checkout conversion", "% of sessions resulting in a paid order"),
            ("Order fulfilment time", "Average days from paid to dispatched"),
            ("Inventory accuracy", "% match of physical and recorded stock"),
        ]],
        "risks": [item(title=t, impact=i, mitigation=m, likelihood=l, status="Open", owner="Unassigned") for t,i,m,l in [
            ("Unsupported health claims", "Regulatory and customer safety risk", "Review product claims, instructions and classification with qualified regulatory advisers before launch.", "High"),
            ("Payment integration delays", "Unable to accept payments at launch", "Complete merchant onboarding early; use sandbox test cases; confirm webhook signature checks.", "Medium"),
            ("Inaccurate inventory", "Overselling and delayed dispatch", "Track stock per SKU and use reconciliation/low-stock alerts.", "Medium"),
            ("Courier delays", "Customer dissatisfaction", "Document delivery SLAs and surface transparent order statuses.", "Medium"),
            ("Commission disputes", "Agent trust and financial exposure", "Agree written commission rules, attribution windows, reversals and approvals.", "Medium"),
            ("Security or privacy incident", "Customer data exposure and reputational harm", "Role-based access, HTTPS, backups, dependency updates and POPIA review.", "High"),
            ("Scope changes", "Extra cost and schedule slippage", "Record change requests, decisions and revised backlog priorities.", "Medium"),
        ]],
        "next_steps": [item(title=t, detail=d, status="Not started") for t,d in [
            ("Approve project scope", "Agree MVP, exclusions, price/budget and business sign-off."),
            ("Confirm product catalogue", "Verify photos, ingredients, labels, categories, pricing and medical claims."),
            ("Agree responsibilities", "Nominate client decision-maker and ECS delivery owner."),
            ("Review sprint backlog", "Prioritise user stories and acceptance criteria."),
            ("Start Sprint 1", "Kickoff, discovery and UI mockups after approval."),
            ("Inspect and adapt", "Demo each increment, record decisions and refine the next sprint."),
        ]],
    }


class ConflictError(Exception):
    pass


class ValidationError(Exception):
    pass


class Store:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=15000")
            with conn:
                yield conn
        finally:
            conn.close()

    def initialize(self):
        with self.connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin','editor','viewer')),
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS current_state (
                id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL,
                state_json TEXT NOT NULL, modified_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS revisions (
                version INTEGER PRIMARY KEY,
                snapshot_json TEXT NOT NULL,
                actor TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS login_failures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                ip TEXT NOT NULL,
                created_epoch INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS login_attempt_idx ON login_failures(username,ip,created_epoch);
            CREATE TABLE IF NOT EXISTS client_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_type TEXT NOT NULL CHECK(subject_type IN ('design','step')),
                subject_id TEXT NOT NULL,
                author TEXT NOT NULL,
                feedback_type TEXT NOT NULL CHECK(feedback_type IN ('Comment','Prefer this design','Request changes')),
                comment TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS feedback_subject_idx ON client_feedback(subject_type,subject_id,id);
            CREATE TABLE IF NOT EXISTS access_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                event TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)
            exists = conn.execute("SELECT 1 FROM current_state WHERE id=1").fetchone()
            if not exists:
                now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
                state = json.dumps(seed_state(), ensure_ascii=False)
                conn.execute("INSERT INTO current_state VALUES (1,1,?,?)", (state, now))
                conn.execute("INSERT INTO revisions VALUES (1,?,?,?,?)", (state, "system", "Initial Isazi client project plan", now))
            else:
                existing = conn.execute("SELECT version,state_json FROM current_state WHERE id=1").fetchone()
                state = json.loads(existing["state_json"])
                defaults = seed_state()
                missing = [k for k in ("client_steps", "designs", "commercial_scope") if k not in state]
                for key in missing:
                    state[key] = defaults[key]
                sanitized = sanitize_commercial_scope(state["commercial_scope"])
                if missing or sanitized:
                    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
                    version = existing["version"] + 1
                    snapshot = json.dumps(state, ensure_ascii=False)
                    conn.execute("UPDATE current_state SET version=?,state_json=?,modified_at=? WHERE id=1", (version,snapshot,now))
                    description = "Scope-only presentation: removed legacy project amount" if sanitized else "Added missing client workspace and scope fields"
                    conn.execute("INSERT INTO revisions(version,snapshot_json,actor,message,created_at) VALUES (?,?,?,?,?)", (version,snapshot,"system",description,now))

    def current(self) -> tuple[int, dict]:
        with self.connect() as conn:
            row = conn.execute("SELECT version,state_json FROM current_state WHERE id=1").fetchone()
        if not row:
            raise RuntimeError("Database not initialized; run python app.py init")
        return row["version"], json.loads(row["state_json"])

    def versions(self):
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT version,actor,message,created_at FROM revisions ORDER BY version DESC").fetchall()]

    def revision(self, version: int):
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM revisions WHERE version=?", (version,)).fetchone()
        return {**dict(row), "state": json.loads(row["snapshot_json"])} if row else None

    def save(self, expected_version: int, actor: str, message: str, operation: dict):
        if not message or len(message) > 240:
            raise ValidationError("Please provide a short change description (up to 240 characters).")
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT version,state_json FROM current_state WHERE id=1").fetchone()
            if not row:
                raise RuntimeError("Not initialized")
            if int(row["version"]) != int(expected_version):
                raise ConflictError(f"The plan changed since you opened the form (current version {row['version']}). Refresh before saving.")
            state = json.loads(row["state_json"])
            action = operation.get("action")
            collection = operation.get("collection")
            if action == "overview":
                changes = operation.get("values", {})
                if not changes or any(k not in OVERVIEW_FIELDS for k in changes):
                    raise ValidationError("Invalid overview fields")
                for field, val in changes.items():
                    state["overview"][field] = clean(val, 6000)
            elif action in ("create", "update", "delete") and collection in SCHEMA:
                items = state[collection]
                ident = operation.get("id")
                if action == "create":
                    new = self._validated(collection, operation.get("values", {}))
                    new["id"] = str(uuid.uuid4())
                    items.append(new)
                else:
                    target = next((x for x in items if x["id"] == ident), None)
                    if not target:
                        raise ValidationError("The selected item no longer exists")
                    if action == "delete":
                        items.remove(target)
                    else:
                        target.update(self._validated(collection, operation.get("values", {})))
            elif action == "commercial_scope":
                changes = operation.get("values", {})
                allowed = set(COMMERCIAL_SCOPE_FIELDS)
                if not isinstance(changes, dict) or not changes or any(k not in allowed for k in changes):
                    raise ValidationError("Invalid commercial scope fields")
                prior = state.setdefault("commercial_scope", default_commercial_scope())
                for field, value in changes.items():
                    cleaned = clean(value, 6000 if field in ("included", "excluded", "third_party", "client_duties", "change_control") else 1200)
                    if field == "scope_status" and cleaned not in SCOPE_STATUS:
                        raise ValidationError("Select a valid scope confirmation state")
                    prior[field] = cleaned
                sanitize_commercial_scope(prior)
                if prior["scope_status"] == "Approved in writing" and not prior["signoff_reference"].strip():
                    raise ValidationError("Record the written sign-off reference before marking scope approved")
            elif action == "restore":
                old_version = int(operation["restore_version"])
                old = conn.execute("SELECT snapshot_json FROM revisions WHERE version=?", (old_version,)).fetchone()
                if not old:
                    raise ValidationError("Selected revision not found")
                restored = json.loads(old["snapshot_json"])
                for module in ("client_steps", "designs", "commercial_scope"):
                    if module not in restored:
                        restored[module] = state.get(module, seed_state()[module])
                state = restored
                sanitize_commercial_scope(state["commercial_scope"])
            elif action == "checkpoint":
                pass
            else:
                raise ValidationError("Unknown modification type")
            # Keep the currently displayed project scope amount-free, including
            # edits restored from an earlier pre-update revision.
            if "commercial_scope" in state:
                sanitize_commercial_scope(state["commercial_scope"])
            new_version = int(row["version"]) + 1
            now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            snapshot = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
            conn.execute("UPDATE current_state SET version=?,state_json=?,modified_at=? WHERE id=1", (new_version, snapshot, now))
            conn.execute("INSERT INTO revisions VALUES (?,?,?,?,?)", (new_version, snapshot, actor, message, now))
            return new_version

    @staticmethod
    def _validated(collection, values):
        fields = SCHEMA[collection][1]
        if not isinstance(values, dict) or any(k not in {f[0] for f in fields} for k in values):
            raise ValidationError("Invalid item fields")
        data = {}
        for field, label, typ in fields:
            val = clean(values.get(field, ""), 6000 if typ == "textarea" else 240)
            if typ in CHOICES and val not in CHOICES[typ]:
                raise ValidationError(f"Invalid option for {label}")
            if field == "title" and not val:
                raise ValidationError("Item title is required")
            data[field] = val
        return data


def clean(value: Any, max_length: int) -> str:
    if not isinstance(value, str):
        raise ValidationError("Fields must contain text")
    value = value.strip().replace("\x00", "")
    if len(value) > max_length:
        raise ValidationError(f"Text field exceeds the {max_length} character limit")
    return value


def completion(state):
    statuses = [x["status"] for x in state["stories"]]
    total = len(statuses)
    done = sum(1 for x in statuses if x == "Done")
    points = sum(int(x.get("points") or "0") for x in state["stories"])
    done_points = sum(int(x.get("points") or "0") for x in state["stories"] if x["status"] == "Done")
    return {"total": total, "done": done, "percentage": round(100*done/total) if total else 0,
            "points": points, "done_points": done_points,
            "open_risks": sum(x["status"] != "Closed" for x in state["risks"]),
            "completed_sprints": sum(x["status"] == "Completed" for x in state["sprints"])}


def feedback_list(store: Store, subject_type: str, subject_id: str):
    with store.connect() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT id,subject_type,subject_id,author,feedback_type,comment,created_at FROM client_feedback WHERE subject_type=? AND subject_id=? ORDER BY id DESC", (subject_type,subject_id))]


def add_feedback(store: Store, subject_type: str, subject_id: str, author: str, feedback_type: str, comment: str):
    if subject_type not in ("design", "step") or feedback_type not in ("Comment", "Prefer this design", "Request changes"):
        raise ValidationError("Invalid feedback type")
    if subject_type == "step" and feedback_type == "Prefer this design":
        raise ValidationError("A preference can only apply to a design")
    comment = clean(comment, 1500)
    if not comment or len(comment) < 3:
        raise ValidationError("Please enter a note with at least three characters")
    _, current = store.current()
    collection = "designs" if subject_type == "design" else "client_steps"
    if not any(it["id"] == subject_id for it in current[collection]):
        raise ValidationError("This item was not found")
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with store.connect() as conn:
        conn.execute("INSERT INTO client_feedback(subject_type,subject_id,author,feedback_type,comment,created_at) VALUES (?,?,?,?,?,?)",
                     (subject_type,subject_id,author,feedback_type,comment,now))
