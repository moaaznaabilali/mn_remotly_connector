# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools
from .remotly_backend import PRIO_TO_REMOTLY

PUSH_FIELDS = {"name", "description", "stage_id", "user_ids", "priority", "date_deadline"}


class ProjectTask(models.Model):
    _inherit = "project.task"

    remotly_id = fields.Char(string="Remotly Task ID", copy=False, readonly=True)
    remotly_backend_id = fields.Many2one(related="project_id.remotly_backend_id", store=True)
    remotly_sync = fields.Boolean(related="project_id.remotly_sync", store=True)
    remotly_column_id = fields.Char(copy=False, readonly=True)

    def _remotly_push(self):
        for t in self:
            project = t.project_id
            backend = project.remotly_backend_id
            if not project or not project.remotly_sync or not backend or not t.name:
                continue
            if not project.remotly_id:
                project._remotly_push()
            if not project.remotly_id:
                continue
            stage_name = t.stage_id._remotly_name() if t.stage_id else "To Do"
            column_id = project._remotly_ensure_column(stage_name)
            assignee = t.user_ids[:1]
            assignee_id = backend._remotly_user_id(assignee) if assignee else False
            desc = tools.html2plaintext(t.description) if t.description else ""
            base = {
                "title": t.name,
                "description": desc,
                "priority": PRIO_TO_REMOTLY.get(t.priority, "MEDIUM"),
                "assigneeId": assignee_id or None,
                "dueDate": t.date_deadline.isoformat() if t.date_deadline else None,
            }
            if not t.remotly_id:
                res = backend._api("POST", "/api/tasks", payload=dict(base, columnId=column_id))
                t.with_context(remotly_no_sync=True).write({
                    "remotly_id": res.get("id"), "remotly_column_id": column_id})
            else:
                backend._api("PUT", "/api/tasks/%s" % t.remotly_id, payload=base)
                if column_id and column_id != t.remotly_column_id:
                    backend._api("PUT", "/api/tasks/%s/move" % t.remotly_id,
                                 payload={"columnId": column_id})
                    t.with_context(remotly_no_sync=True).write({"remotly_column_id": column_id})
        return True

    # ------------------------------------------------------------------ triggers
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get("remotly_no_sync"):
            for t in records:
                if t.remotly_sync and t.remotly_backend_id and t.remotly_backend_id.auto_push:
                    t._remotly_push()
        return records

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("remotly_no_sync"):
            return res
        if PUSH_FIELDS & set(vals.keys()):
            for t in self:
                if t.remotly_sync and t.remotly_backend_id and t.remotly_backend_id.auto_push:
                    t._remotly_push()
        return res
