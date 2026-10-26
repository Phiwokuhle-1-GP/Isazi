"""Isazi Agile Studio — client-facing editable Agile plan with audit snapshots."""
from __future__ import annotations

import argparse
import csv
import difflib
import getpass
import io
import json
import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from state import CHOICES, OVERVIEW_FIELDS, SCHEMA, COMMERCIAL_SCOPE_FIELDS, SCOPE_STATUS, default_commercial_scope, ConflictError, Store, ValidationError, completion, feedback_list, add_feedback
from status_report import build_status_pdf

BASE_DIR = Path(__file__).resolve().parent
TITLES = {
    1: "Agile approach & objectives",
    2: "Stakeholders & solution scope",
    3: "Sprints & delivery roadmap",
    4: "Stories, journeys & performance",
}
COLLECTION_NAMES = {
    "client_steps": "Client progress tracker", "designs": "Design catalogue",
    "principles": "Agile principles", "objectives": "Project objectives", "stakeholders": "Stakeholders",
    "scope_in": "In scope", "scope_out": "Out of scope", "systems": "Solution components",
    "sprints": "Sprints", "milestones": "Project milestones", "stories": "User stories",
    "journeys": "User journeys", "kpis": "KPIs", "risks": "Project risks", "next_steps": "Next actions",
}


def create_app(test_config=None):
    app = Flask(__name__, instance_path=str(BASE_DIR / "instance"), instance_relative_config=True)
    app.instance_path and Path(app.instance_path).mkdir(exist_ok=True, parents=True)
    secret_file = Path(app.instance_path) / ".secret-key"
    if os.environ.get("ISAZI_SECRET_KEY"):
        secret = os.environ["ISAZI_SECRET_KEY"]
    else:
        if not secret_file.exists():
            secret_file.write_text(secrets.token_urlsafe(48), encoding="utf-8")
            try:
                os.chmod(secret_file, 0o600)
            except OSError:
                pass
        secret = secret_file.read_text(encoding="utf-8").strip()
    app.config.update(
        SECRET_KEY=secret,
        DATABASE=os.environ.get("ISAZI_DB_PATH", str(Path(app.instance_path) / "isazi.sqlite3")),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("ISAZI_HTTPS", "0") == "1",
        PERMANENT_SESSION_LIFETIME=__import__("datetime").timedelta(hours=8),
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    store = Store(app.config["DATABASE"])
    store.initialize()
    app.extensions["isazi_store"] = store

    @app.before_request
    def load_user():
        g.user = None
        uid = session.get("user_id")
        if uid:
            with store.connect() as conn:
                row = conn.execute("SELECT id,username,role,enabled FROM users WHERE id=?", (uid,)).fetchone()
            if row and row["enabled"]:
                g.user = dict(row)
            else:
                session.clear()
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)

    @app.after_request
    def set_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        # Only authenticated, same-origin mock storefront frames may be embedded in the client review page.
        preview = request.endpoint == "storefront_preview"
        response.headers["X-Frame-Options"] = "SAMEORIGIN" if preview else "DENY"
        ancestor = "'self'" if preview else "'none'"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors " + ancestor
        if g.get("user"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.context_processor
    def context():
        return {"csrf_token": lambda: session.get("csrf", ""), "collection_names": COLLECTION_NAMES,
                "page_titles": TITLES, "current_user": g.get("user"), "has_edit_rights": bool(g.get("user") and g.user["role"] in ("editor", "admin"))}

    def csrf_check():
        if not secrets.compare_digest(request.form.get("csrf_token", ""), session.get("csrf", "")):
            abort(403, "Session token expired. Reload the page and try again.")

    def logged_in(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not g.user:
                return redirect(url_for("login", next=request.path))
            return view(*args, **kwargs)
        return wrapped

    def editor(view):
        @wraps(view)
        @logged_in
        def wrapped(*args, **kwargs):
            if g.user["role"] not in ("editor", "admin"):
                abort(403, "This account has view-only access.")
            return view(*args, **kwargs)
        return wrapped

    def admin(view):
        @wraps(view)
        @logged_in
        def wrapped(*args, **kwargs):
            if g.user["role"] != "admin":
                abort(403, "Admin access is required.")
            return view(*args, **kwargs)
        return wrapped

    @app.get("/")
    def index():
        # Public placeholder only; plan, account records and owner workspace stay private.
        return render_template("coming_soon.html", title="Website under construction")

    @app.get("/owner")
    @admin
    def owner_dashboard():
        version, data = store.current()
        stories = data.get("stories", [])
        sprints = data.get("sprints", [])
        completed = sum(1 for item in stories if item.get("status") == "Done")
        in_progress = sum(1 for item in stories if item.get("status") in ("In progress", "In review"))
        return render_template("owner.html", title="Owner dashboard", version=version,
            story_count=len(stories), completed=completed, in_progress=in_progress,
            sprint_count=len(sprints), plan=data,
            client_steps=data.get("client_steps", []), designs=data.get("designs", []), commercial_scope=data.get("commercial_scope", default_commercial_scope()))

    @app.route("/account/password", methods=["GET", "POST"])
    @logged_in
    def change_password():
        if request.method == "POST":
            csrf_check()
            old = request.form.get("current_password", "")
            new = request.form.get("new_password", "")
            confirm = request.form.get("confirm_password", "")
            with store.connect() as conn:
                user = conn.execute("SELECT password_hash FROM users WHERE id=?", (g.user["id"],)).fetchone()
            if not user or not check_password_hash(user["password_hash"], old):
                flash("Current password is incorrect.", "error")
            elif len(new) < 12 or new != confirm:
                flash("New password must be at least 12 characters and match confirmation.", "error")
            elif new == old:
                flash("Choose a different password.", "error")
            else:
                with store.connect() as conn:
                    conn.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new), g.user["id"]))
                    conn.execute("DELETE FROM login_failures WHERE username=?", (g.user["username"],))
                    conn.execute("INSERT INTO access_audit(username,event,created_at) VALUES (?,?,?)", (g.user["username"], "Changed own password", utcnow()))
                session.clear()
                flash("Password changed. Please sign in again.", "success")
                return redirect(url_for("login"))
        return render_template("change_password.html", title="Change password")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.user:
            return redirect(url_for("owner_dashboard" if g.user["role"] == "admin" else "client_progress"))
        if request.method == "POST":
            csrf_check()
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")
            remote = request.remote_addr or "unknown"
            now_epoch = int(time.time())
            with store.connect() as conn:
                conn.execute("DELETE FROM login_failures WHERE created_epoch<?", (now_epoch - 3600,))
                attempt_count = conn.execute("SELECT COUNT(*) FROM login_failures WHERE username=? AND ip=? AND created_epoch>?",
                                             (username, remote, now_epoch - 900)).fetchone()[0]
                record = conn.execute("SELECT * FROM users WHERE username=? AND enabled=1", (username,)).fetchone()
            if attempt_count >= 8:
                flash("Too many failed attempts. Try again later.", "error")
                return render_template("login.html", title="Secure sign in"), 429
            valid = bool(record and check_password_hash(record["password_hash"], password))
            if valid:
                session.clear()
                session["csrf"] = secrets.token_urlsafe(32)
                session["user_id"] = record["id"]
                session.permanent = True
                with store.connect() as conn:
                    conn.execute("INSERT INTO access_audit(username,event,created_at) VALUES (?,?,?)", (username,"login",utcnow()))
                return redirect(url_for("owner_dashboard" if record["role"] == "admin" else "client_progress"))
            with store.connect() as conn:
                conn.execute("INSERT INTO login_failures(username,ip,created_epoch) VALUES (?,?,?)", (username,remote,now_epoch))
            flash("Incorrect username or password.", "error")
        return render_template("login.html", title="Secure sign in")

    @app.post("/logout")
    @logged_in
    def logout():
        csrf_check()
        session.clear()
        return redirect(url_for("login"))

    @app.get("/page/<int:page_num>")
    @logged_in
    def page(page_num):
        if page_num not in TITLES:
            abort(404)
        version, data = store.current()
        return render_template(f"page{page_num}.html", data=data, version=version, metrics=completion(data),
                               page_num=page_num, title=TITLES[page_num], choices=CHOICES)

    @app.get("/edit/overview")
    @editor
    def overview_form():
        version, data = store.current()
        return render_template("edit.html", collection="overview", record=data["overview"], id="",
                               fields=[(k,v,"textarea" if k in ("summary","agile_intro","agile_cycle","vision","assumptions") else "text") for k,v in OVERVIEW_FIELDS.items()],
                               version=version, title="Edit project overview", choices=CHOICES, return_page=1)

    @app.get("/edit/<collection>")
    @editor
    def edit_form(collection):
        if collection not in SCHEMA:
            abort(404)
        version, data = store.current()
        ident = request.args.get("id")
        record = next((x for x in data[collection] if x["id"] == ident), None) if ident else None
        if ident and record is None:
            abort(404)
        return render_template("edit.html", collection=collection, record=record, id=ident,
                               fields=SCHEMA[collection][1], version=version,
                               title=("Edit " if record else "Add ") + COLLECTION_NAMES[collection].lower(),
                               choices=CHOICES, return_page=SCHEMA[collection][0])

    @app.post("/save/overview")
    @editor
    def save_overview():
        csrf_check()
        values = {k: request.form.get(k, "") for k in OVERVIEW_FIELDS}
        return persist(request.form.get("version"), request.form.get("message") or "Updated project overview",
                       {"action": "overview", "values": values}, 1)

    @app.post("/save/<collection>")
    @editor
    def save_collection(collection):
        csrf_check()
        if collection not in SCHEMA:
            abort(404)
        values = {k: request.form.get(k, "") for k, _, _ in SCHEMA[collection][1]}
        ident = request.form.get("id")
        action = "update" if ident else "create"
        message = request.form.get("message") or f"{action.title()} {COLLECTION_NAMES[collection].lower()}"
        return persist(request.form.get("version"), message,
                       {"action": action, "collection": collection, "id": ident, "values": values}, SCHEMA[collection][0])

    @app.post("/delete/<collection>/<ident>")
    @editor
    def delete_item(collection, ident):
        csrf_check()
        if collection not in SCHEMA:
            abort(404)
        return persist(request.form.get("version"), request.form.get("message") or f"Deleted {COLLECTION_NAMES[collection].lower()} item",
                       {"action": "delete", "collection": collection, "id": ident}, SCHEMA[collection][0])

    def persist(expected, message, operation, return_page=1):
        try:
            if not expected or not expected.isdecimal():
                raise ValidationError("Missing edit version. Reload the editor.")
            updated = store.save(int(expected), g.user["username"], message, operation)
        except (ValidationError, ConflictError, ValueError) as exc:
            flash(str(exc), "error")
            if isinstance(exc, ConflictError):
                return redirect(url_for("history")), 303
            return redirect(request.referrer or url_for("page", page_num=return_page)), 303
        flash(f"Saved successfully as version {updated}.", "success")
        if operation.get("action") == "commercial_scope":
            return redirect(url_for("client_scope"))
        if operation.get("collection") == "client_steps":
            return redirect(url_for("client_progress"))
        if operation.get("collection") == "designs":
            return redirect(url_for("design_catalogue"))
        return redirect(url_for("page", page_num=return_page))

    @app.post("/checkpoint")
    @editor
    def checkpoint():
        csrf_check()
        return persist(request.form.get("version"), request.form.get("message") or "Client review checkpoint",
                       {"action": "checkpoint"}, 1)

    @app.get("/history")
    @logged_in
    def history():
        version, _ = store.current()
        revisions = store.versions()
        return render_template("history.html", versions=revisions, version=version, title="Version history")

    @app.get("/history/compare")
    @logged_in
    def compare():
        version, _ = store.current()
        try:
            a = int(request.args.get("from", "1"))
            b = int(request.args.get("to", str(version)))
        except ValueError:
            abort(400)
        va, vb = store.revision(a), store.revision(b)
        if not va or not vb:
            abort(404)
        before = json.dumps(va["state"], indent=2, ensure_ascii=False, sort_keys=True).splitlines()
        after = json.dumps(vb["state"], indent=2, ensure_ascii=False, sort_keys=True).splitlines()
        diff = list(difflib.unified_diff(before, after, fromfile=f"Version {a}", tofile=f"Version {b}", lineterm=""))
        return render_template("compare.html", title="Compare versions", before=va, after=vb,
                               diff=diff, version=version)

    @app.get("/history/<int:rev>")
    @logged_in
    def revision_detail(rev):
        snapshot = store.revision(rev)
        if not snapshot:
            abort(404)
        version, _ = store.current()
        return render_template("revision.html", snapshot=snapshot, pretty=json.dumps(snapshot["state"], ensure_ascii=False, indent=2),
                               version=version, title=f"Version {rev}")

    @app.post("/history/<int:rev>/restore")
    @editor
    def restore(rev):
        csrf_check()
        return persist(request.form.get("version"), f"Restored content of version {rev}",
                       {"action": "restore", "restore_version": rev}, 1)

    @app.get("/export/revision/<int:rev>.json")
    @logged_in
    def export_revision(rev):
        snapshot = store.revision(rev)
        if not snapshot:
            abort(404)
        payload = json.dumps({"version": rev, "exported_utc": utcnow(), "plan": snapshot["state"]}, ensure_ascii=False, indent=2)
        return send_file(io.BytesIO(payload.encode("utf-8")), as_attachment=True,
                         download_name=f"isazi_agile_plan_v{rev}.json", mimetype="application/json")

    @app.get("/export/json")
    @logged_in
    def export_json():
        version, data = store.current()
        with store.connect() as conn:
            notes = [dict(x) for x in conn.execute("SELECT id,subject_type,subject_id,author,feedback_type,comment,created_at FROM client_feedback ORDER BY id")]
        payload = json.dumps({"version": version, "exported_utc": utcnow(), "plan": data, "client_feedback": notes}, ensure_ascii=False, indent=2)
        return send_file(io.BytesIO(payload.encode("utf-8")), as_attachment=True,
                         download_name=f"isazi_agile_plan_v{version}.json", mimetype="application/json")

    @app.get("/export/client-feedback.csv")
    @logged_in
    def export_client_feedback():
        with store.connect() as conn:
            rows = [dict(x) for x in conn.execute(
                "SELECT id,subject_type,subject_id,author,feedback_type,comment,created_at FROM client_feedback ORDER BY id")]
        fields = ["id","subject_type","subject_id","author","feedback_type","comment","created_at"]
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        return send_file(io.BytesIO(("\ufeff"+output.getvalue()).encode("utf-8")),as_attachment=True,
                         download_name="isazi_client_feedback.csv",mimetype="text/csv")

    @app.get("/export/stories.csv")
    @logged_in
    def export_stories():
        _, data = store.current()
        columns = [field for field, _, _ in SCHEMA["stories"][1]]
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data["stories"])
        return send_file(io.BytesIO(("\ufeff" + stream.getvalue()).encode("utf-8")), as_attachment=True,
                         download_name="isazi_user_stories.csv", mimetype="text/csv")

    # Client review module. These routes are part of the v3 templates and
    # must be registered before templates call url_for() for them.
    @app.get("/client/progress")
    @logged_in
    def client_progress():
        version, data = store.current()
        steps = data.get("client_steps", [])
        designs = data.get("designs", [])
        chosen = next((d for d in designs if d.get("status") in ("Approved", "Selected")), None)
        counts = sum(s.get("status") in ("Approved", "Completed") for s in steps)
        notes = {s["id"]: feedback_list(store, "step", s["id"]) for s in steps}
        attention = [s for s in steps if s.get("status") in ("Awaiting client", "In review")]
        return render_template("client_progress.html", title="Client progress tracker",
                               version=version, steps=steps, completed=counts,
                               total=len(steps), selected=chosen, notes=notes, attention=attention,
                               commercial_scope=data.get("commercial_scope", default_commercial_scope()))

    @app.get("/client")
    @logged_in
    def client_home():
        return redirect(url_for("client_progress"))

    @app.get("/client/scope")
    @logged_in
    def client_scope():
        version, data = store.current()
        return render_template("client_scope.html", title="E-commerce project scope", version=version,
                               scope=data.get("commercial_scope", default_commercial_scope()))

    @app.route("/client/scope/edit", methods=["GET", "POST"])
    @editor
    def edit_client_scope():
        if request.method == "POST":
            csrf_check()
            scope = {k: request.form.get(k, "") for k in COMMERCIAL_SCOPE_FIELDS}
            return persist(request.form.get("version"),
                           request.form.get("message") or "Updated project scope and separately quoted services",
                           {"action": "commercial_scope", "values": scope}, 2)
        version, data = store.current()
        return render_template("edit_client_scope.html", title="Edit project scope", version=version,
                               scope=data.get("commercial_scope", default_commercial_scope()),
                               fields=COMMERCIAL_SCOPE_FIELDS, statuses=SCOPE_STATUS)

    @app.get("/client/status-report.pdf")
    @logged_in
    def download_status_pdf():
        version, data = store.current()
        with store.connect() as conn:
            notes = [dict(x) for x in conn.execute(
                "SELECT subject_type,subject_id,author,feedback_type,comment,created_at FROM client_feedback ORDER BY id")]
        pdf = build_status_pdf(data, version, notes)
        return send_file(io.BytesIO(pdf), mimetype="application/pdf", as_attachment=True,
                         download_name=f"Isazi_Project_Status_v{version}.pdf", max_age=0)

    @app.get("/client/designs")
    @logged_in
    def design_catalogue():
        version, data = store.current()
        designs = data.get("designs", [])
        feedback_counts = {d["id"]: len(feedback_list(store, "design", d["id"])) for d in designs}
        return render_template("design_catalogue.html", title="Website design catalogue",
                               version=version, designs=designs, feedback_counts=feedback_counts)

    @app.get("/client/designs/<ident>")
    @logged_in
    def design_detail(ident):
        version, data = store.current()
        design = next((d for d in data.get("designs", []) if d["id"] == ident), None)
        if design is None:
            abort(404)
        notes = feedback_list(store, "design", ident)
        return render_template("design_detail.html", title=design["title"],
                               version=version, design=design, notes=notes)

    @app.get("/client/designs/<ident>/preview")
    @logged_in
    def storefront_preview(ident):
        _, data = store.current()
        design = next((d for d in data.get("designs", []) if d["id"] == ident), None)
        if design is None:
            abort(404)
        # Exact sample individual prices come from the client-provided catalogue.
        # These are not inventory records and the preview never accepts orders.
        products = [
            {"name":"Smolo", "price":"250", "price_number":250, "photo":"design_smolo.jpg",
             "label":"Bottled herbal product", "category":"bottles", "blurb":"Traditional product in the supplied Isazi catalogue."},
            {"name":"Soursop Leaves", "price":"350", "price_number":350, "photo":"design_soursop.jpg",
             "label":"Leaves & botanicals", "category":"botanicals", "blurb":"Soursop leaf product; final ingredients and labelling pending."},
            {"name":"Sea Moss", "price":"450", "price_number":450, "photo":"design_sea_moss.jpg",
             "label":"Botanical selection", "category":"botanicals", "blurb":"Sea moss product, presented for client concept review."},
            {"name":"Eye Care Solution", "price":"100", "price_number":100, "photo":"design_eye_care.jpg",
             "label":"Bottled solution", "category":"solutions", "blurb":"Catalogue reference only; safety and permitted claims require review."},
        ]
        for product in products:
            product["image_url"] = url_for("static", filename="img/"+product["photo"])
        return render_template("storefront_preview.html", title="Storefront concept preview",
                               design=design, products=products)

    @app.post("/client/feedback/<subject_type>/<ident>")
    @logged_in
    def submit_client_feedback(subject_type, ident):
        csrf_check()
        if subject_type not in ("step", "design"):
            abort(404)
        try:
            add_feedback(store, subject_type, ident, g.user["username"],
                         request.form.get("feedback_type", "Comment"),
                         request.form.get("comment", ""))
            flash("Feedback saved with your name and timestamp.", "success")
        except ValidationError as exc:
            flash(str(exc), "error")
        if subject_type == "step":
            return redirect(url_for("client_progress"), code=303)
        return redirect(url_for("design_detail", ident=ident), code=303)

    def save_client_status(collection, ident, status, expected_version, message):
        # Submit a full validated record to the version-controlled store.
        version, data = store.current()
        record = next((r for r in data.get(collection, []) if r["id"] == ident), None)
        if record is None:
            abort(404)
        option_key = "client_status" if collection == "client_steps" else "design_status"
        if status not in CHOICES[option_key]:
            flash("Choose one of the available statuses.", "error")
            return redirect(url_for("client_progress" if collection == "client_steps" else "design_detail",
                                    **({} if collection == "client_steps" else {"ident": ident})), code=303)
        values = {field: record.get(field, "") for field, _, _ in SCHEMA[collection][1]}
        values["status"] = status
        return persist(expected_version, message, {"action": "update", "collection": collection,
                                                  "id": ident, "values": values},
                       SCHEMA[collection][0])

    @app.post("/client/progress/<ident>/status")
    @editor
    def update_client_status(ident):
        csrf_check()
        return save_client_status("client_steps", ident, request.form.get("status", ""),
                                  request.form.get("version", ""), "Updated client progress status")

    @app.post("/client/designs/<ident>/status")
    @editor
    def update_design_status(ident):
        csrf_check()
        return save_client_status("designs", ident, request.form.get("status", ""),
                                  request.form.get("version", ""), "Updated website design status")

    @app.route("/users", methods=["GET", "POST"])
    @admin
    def users():
        if request.method == "POST":
            csrf_check()
            action = request.form.get("action")
            name = request.form.get("username", "").strip().lower()
            role = request.form.get("role", "viewer")
            password = request.form.get("password", "")
            try:
                with store.connect() as conn:
                    if action == "create":
                        if not (name and 3 <= len(name) <= 40 and name.replace("_", "").replace("-", "").isalnum()):
                            raise ValidationError("Username must be 3–40 characters, using letters, numbers, _ or -.")
                        if role not in ("admin", "editor", "viewer") or len(password) < 12:
                            raise ValidationError("Choose a valid role and a password of at least 12 characters.")
                        conn.execute("INSERT INTO users (username,password_hash,role,enabled,created_at) VALUES (?,?,?,?,?)",
                                     (name,generate_password_hash(password),role,1,utcnow()))
                        msg = f"Created {role} account {name}"
                    elif action in ("disable", "enable", "reset"):
                        uid = int(request.form.get("user_id", "0"))
                        target = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
                        if not target:
                            raise ValidationError("User not found")
                        if target["id"] == g.user["id"] and action == "disable":
                            raise ValidationError("You cannot disable your own account")
                        if action == "reset":
                            if len(password) < 12:
                                raise ValidationError("New password must contain at least 12 characters")
                            conn.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(password),uid))
                        else:
                            conn.execute("UPDATE users SET enabled=? WHERE id=?", (1 if action=="enable" else 0,uid))
                        msg = f"{action.title()} account {target['username']}"
                    else:
                        raise ValidationError("Unknown user action")
                    conn.execute("INSERT INTO access_audit (username,event,created_at) VALUES (?,?,?)", (g.user["username"],msg,utcnow()))
                flash(msg, "success")
            except (ValidationError, ValueError, sqlite3.IntegrityError) as exc:
                flash(str(exc), "error")
            return redirect(url_for("users"))
        with store.connect() as conn:
            all_users = [dict(x) for x in conn.execute("SELECT id,username,role,enabled,created_at FROM users ORDER BY username")]
            audit = [dict(x) for x in conn.execute("SELECT username,event,created_at FROM access_audit ORDER BY id DESC LIMIT 25")]
        return render_template("users.html", title="Access management", users=all_users, audit=audit)

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.errorhandler(403)
    def forbidden(err):
        return render_template("error.html", title="Access denied", status=403, message=str(err.description)), 403

    @app.errorhandler(404)
    def not_found(err):
        return render_template("error.html", title="Not found", status=404, message="This page or item could not be found."), 404

    return app


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cli():
    parser = argparse.ArgumentParser(description="Isazi Agile Studio")
    sub = parser.add_subparsers(dest="command")
    init = sub.add_parser("init", help="Create database and initial admin account")
    init.add_argument("--username", default="owner")
    reset = sub.add_parser("reset-password", help="Reset an existing account password locally")
    reset.add_argument("--username", default="owner")
    server = sub.add_parser("serve", help="Run local development server")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=5000)
    server.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    app = create_app()
    store = app.extensions["isazi_store"]
    if args.command == "init":
        username = args.username.strip().lower()
        if not (3 <= len(username) <= 40 and username.replace("_", "").replace("-", "").isalnum()):
            parser.error("Use a valid username (3–40 characters)")
        with store.connect() as conn:
            user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if user_count:
            print("Database exists and users are configured. Sign in to manage accounts.")
            return
        password = getpass.getpass("Choose owner password (12+ characters): ")
        confirmation = getpass.getpass("Confirm password: ")
        if len(password) < 12 or password != confirmation:
            parser.error("Password needs 12+ characters and must match confirmation")
        with store.connect() as conn:
            conn.execute("INSERT INTO users (username,password_hash,role,enabled,created_at) VALUES (?,?,?,?,?)",
                         (username,generate_password_hash(password),"admin",1,utcnow()))
        print("Owner account created. Start the local server: python app.py serve")
    elif args.command == "reset-password":
        username = args.username.strip().lower()
        with store.connect() as conn:
            existing = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if not existing:
            parser.error("Account not found")
        password = getpass.getpass("New password (12+ characters): ")
        confirmation = getpass.getpass("Confirm new password: ")
        if len(password) < 12 or password != confirmation:
            parser.error("Password needs 12+ characters and must match confirmation")
        with store.connect() as conn:
            conn.execute("UPDATE users SET password_hash=? WHERE username=?", (generate_password_hash(password),username))
            conn.execute("DELETE FROM login_failures WHERE username=?", (username,))
            conn.execute("INSERT INTO access_audit (username,event,created_at) VALUES (?,?,?)", (username, "Local password reset", utcnow()))
        print("Password updated. Restart the app and sign in.")
    else:
        app.run(host=getattr(args,"host","127.0.0.1"), port=getattr(args,"port",5000),
                debug=getattr(args,"debug",False))


if __name__ == "__main__":
    cli()
