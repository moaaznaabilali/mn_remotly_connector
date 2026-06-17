# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:
    requests = None

# Odoo task priority ('0' normal, '1' high) <-> Remotly priority
PRIO_TO_REMOTLY = {"0": "MEDIUM", "1": "HIGH"}
PRIO_FROM_REMOTLY = {"LOW": "0", "MEDIUM": "0", "HIGH": "1", "URGENT": "1"}


class RemotlyBackend(models.Model):
    _name = "remotly.backend"
    _description = "Remotly Backend"

    name = fields.Char(required=True, default="Remotly")
    base_url = fields.Char(string="Base URL", required=True,
                           help="Root URL of the Remotly server, e.g. https://app.remotly.io (without /api).")
    api_key = fields.Char(string="API Key", required=True, copy=False,
                          help="Generated in Remotly: Company settings → Integrations → API keys.")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda s: s.env.company, required=True)
    state = fields.Selection([("draft", "Not connected"), ("connected", "Connected")],
                             default="draft", readonly=True)
    sync_direction = fields.Selection([
        ("both", "Two-way (Odoo ⇄ Remotly)"),
        ("push", "Odoo → Remotly only"),
        ("pull", "Remotly → Odoo only"),
    ], default="both", required=True)
    auto_push = fields.Boolean(string="Push on change", default=True,
                               help="Push projects/tasks to Remotly automatically when they change in Odoo.")
    auto_pull = fields.Boolean(string="Scheduled pull", default=True,
                               help="Pull changes from Remotly on the scheduled action.")
    last_pull = fields.Datetime(readonly=True)
    project_count = fields.Integer(compute="_compute_counts")
    task_count = fields.Integer(compute="_compute_counts")

    def _compute_counts(self):
        Project = self.env["project.project"]
        Task = self.env["project.task"]
        for b in self:
            b.project_count = Project.search_count(
                [("remotly_backend_id", "=", b.id), ("remotly_id", "!=", False)])
            b.task_count = Task.search_count(
                [("remotly_backend_id", "=", b.id), ("remotly_id", "!=", False)])

    # ------------------------------------------------------------------ REST
    def _api(self, method, path, payload=None, params=None):
        self.ensure_one()
        if requests is None:
            raise UserError(_("The Python 'requests' library is required for the Remotly connector."))
        url = (self.base_url or "").rstrip("/") + path
        try:
            resp = requests.request(
                method, url,
                headers={"X-Api-Key": self.api_key or "", "Content-Type": "application/json"},
                json=payload, params=params, timeout=30)
        except Exception as e:
            raise UserError(_("Could not reach Remotly at %s:\n%s") % (url, e))
        if resp.status_code >= 400:
            raise UserError(_("Remotly API error %s on %s:\n%s") % (resp.status_code, path, (resp.text or "")[:400]))
        if resp.text:
            try:
                return resp.json()
            except Exception:
                return {}
        return {}

    def action_test_connection(self):
        self.ensure_one()
        self._api("GET", "/api/projects")
        self.state = "connected"
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": _("Connected"),
                           "message": _("Remotly connection works."), "type": "success"}}

    # ------------------------------------------------------------------ user mapping (by email)
    def _remotly_user_id(self, user):
        """Remotly user id for an Odoo user, matched by email (cached on res.users)."""
        self.ensure_one()
        if not user or not user.email:
            return False
        if user.remotly_user_id and user.remotly_backend_id.id == self.id:
            return user.remotly_user_id
        data = self._api("GET", "/api/directory", params={"q": user.email}) or []
        users = data if isinstance(data, list) else (data.get("users") or data)
        match = next((u for u in users if (u.get("email") or "").lower() == user.email.lower()), None)
        if match:
            user.sudo().write({"remotly_user_id": match["id"], "remotly_backend_id": self.id})
            return match["id"]
        return False

    # ------------------------------------------------------------------ orchestration
    def action_sync_all(self):
        for b in self:
            if b.sync_direction in ("both", "push"):
                projects = self.env["project.project"].search(
                    [("remotly_backend_id", "=", b.id), ("remotly_sync", "=", True)])
                for p in projects:
                    p._remotly_push()
                    for t in p.task_ids:
                        t._remotly_push()
            if b.sync_direction in ("both", "pull"):
                b._pull_changes()
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": _("Sync done"), "type": "success",
                           "message": _("Projects and tasks synchronised with Remotly.")}}

    @api.model
    def cron_pull(self):
        for b in self.search([("active", "=", True), ("auto_pull", "=", True),
                              ("sync_direction", "in", ("both", "pull"))]):
            try:
                b._pull_changes()
            except Exception as e:
                _logger.exception("Remotly pull failed for %s: %s", b.name, e)

    # ------------------------------------------------------------------ pull (Remotly -> Odoo)
    def _pull_changes(self):
        self.ensure_one()
        since = self.last_pull.strftime("%Y-%m-%dT%H:%M:%S.000Z") if self.last_pull else "2000-01-01T00:00:00.000Z"
        data = self._api("GET", "/api/projects/integration/changes", params={"since": since})
        Project = self.env["project.project"]
        Task = self.env["project.task"].with_context(remotly_no_sync=True)
        for rt in data.get("tasks", []):
            odoo_task = self.env["project.task"].search(
                [("remotly_id", "=", rt["id"]), ("remotly_backend_id", "=", self.id)], limit=1)
            rproject_id = ((rt.get("column") or {}).get("board") or {}).get("projectId")
            project = Project.search(
                [("remotly_id", "=", rproject_id), ("remotly_backend_id", "=", self.id)], limit=1)
            if not project:
                continue  # task belongs to a project not synced here
            stage = project._remotly_stage_for_column_name((rt.get("column") or {}).get("name"))
            vals = {
                "name": rt.get("title") or _("Untitled"),
                "description": rt.get("description") or False,
                "priority": PRIO_FROM_REMOTLY.get(rt.get("priority"), "0"),
            }
            if stage:
                vals["stage_id"] = stage.id
            if odoo_task:
                odoo_task.with_context(remotly_no_sync=True).write(vals)
            else:
                vals.update({
                    "project_id": project.id,
                    "remotly_id": rt["id"],
                    "remotly_backend_id": self.id,
                })
                Task.create(vals)
        self.last_pull = fields.Datetime.now()
