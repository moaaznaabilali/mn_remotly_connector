# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

ODOO_COLOR_HEX = {
    0: "#6B7280", 1: "#EF4444", 2: "#F59E0B", 3: "#EAB308", 4: "#06B6D4",
    5: "#8B5CF6", 6: "#EC4899", 7: "#14B8A6", 8: "#3B82F6", 9: "#A855F7",
    10: "#22C55E", 11: "#9333EA",
}


class ProjectProject(models.Model):
    _inherit = "project.project"

    remotly_backend_id = fields.Many2one("remotly.backend", string="Remotly backend", copy=False)
    remotly_sync = fields.Boolean(string="Sync with Remotly", copy=False)
    remotly_id = fields.Char(string="Remotly Project ID", copy=False, readonly=True)
    remotly_board_id = fields.Char(copy=False, readonly=True)

    # ------------------------------------------------------------------ helpers
    def _remotly_color(self):
        self.ensure_one()
        return ODOO_COLOR_HEX.get(self.color or 8, "#3B82F6")

    def _remotly_columns(self):
        """Return {column_name_lower: column_id} for this project's first board (live)."""
        self.ensure_one()
        backend = self.remotly_backend_id
        data = backend._api("GET", "/api/projects/%s" % self.remotly_id)
        cols = {}
        for board in data.get("boards", []):
            for c in board.get("columns", []):
                cols[(c.get("name") or "").strip().lower()] = c.get("id")
        if data.get("boards"):
            self.remotly_board_id = data["boards"][0]["id"]
        return cols

    def _remotly_ensure_column(self, name):
        """Find (or create) a Remotly column by name in this project's board. Return its id."""
        self.ensure_one()
        backend = self.remotly_backend_id
        key = (name or "").strip().lower()
        cols = self._remotly_columns()
        if key in cols:
            return cols[key]
        if not self.remotly_board_id:
            return cols.get("to do") or (list(cols.values())[0] if cols else False)
        created = backend._api(
            "POST", "/api/projects/%s/boards/%s/columns" % (self.remotly_id, self.remotly_board_id),
            payload={"name": name, "position": len(cols)})
        return created.get("id")

    def _remotly_stage_for_column_name(self, name):
        """For pull: return (creating if needed) the Odoo stage matching a Remotly column name."""
        self.ensure_one()
        if not name:
            return self.env["project.task.type"]
        Stage = self.env["project.task.type"]
        stage = self.type_ids.filtered(lambda s: (s._remotly_name() or "").strip().lower() == name.strip().lower())[:1]
        if stage:
            return stage
        stage = Stage.create({"name": name, "project_ids": [(4, self.id)]})
        return stage

    # ------------------------------------------------------------------ push
    def _remotly_push(self):
        for p in self:
            backend = p.remotly_backend_id
            if not p.remotly_sync or not backend:
                continue
            payload = {"name": p.name or _("Project"),
                       "description": p.label_tasks and "" or (p.name or ""),
                       "color": p._remotly_color()}
            payload["description"] = ""  # Odoo project has no plain description; keep empty
            if not p.remotly_id:
                res = backend._api("POST", "/api/projects", payload={
                    "name": p.name or _("Project"), "color": p._remotly_color()})
                p.with_context(remotly_no_sync=True).write({
                    "remotly_id": res.get("id"),
                    "remotly_board_id": (res.get("boards") or [{}])[0].get("id"),
                })
            else:
                backend._api("PUT", "/api/projects/%s" % p.remotly_id, payload={
                    "name": p.name, "color": p._remotly_color()})
        return True

    # ------------------------------------------------------------------ triggers
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for p in records:
            if p.remotly_sync and p.remotly_backend_id and p.remotly_backend_id.auto_push \
                    and not self.env.context.get("remotly_no_sync"):
                p._remotly_push()
        return records

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("remotly_no_sync"):
            return res
        if any(k in vals for k in ("name", "color", "remotly_sync", "remotly_backend_id")):
            for p in self:
                if p.remotly_sync and p.remotly_backend_id and p.remotly_backend_id.auto_push:
                    p._remotly_push()
        return res

    def action_remotly_push_now(self):
        for p in self:
            p._remotly_push()
            for t in p.task_ids:
                t._remotly_push()
        return True
