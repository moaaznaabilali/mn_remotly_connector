# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class RemotlySyncWizard(models.TransientModel):
    _name = "remotly.sync.wizard"
    _description = "Remotly Sync"

    backend_id = fields.Many2one("remotly.backend", string="Backend", required=True,
                                 default=lambda s: s.env["remotly.backend"].search([], limit=1))
    direction = fields.Selection([
        ("both", "Two-way"), ("push", "Push Odoo → Remotly"), ("pull", "Pull Remotly → Odoo"),
    ], default="both", required=True)

    def action_run(self):
        self.ensure_one()
        b = self.backend_id
        if self.direction in ("both", "push"):
            projects = self.env["project.project"].search(
                [("remotly_backend_id", "=", b.id), ("remotly_sync", "=", True)])
            for p in projects:
                p._remotly_push()
                for t in p.task_ids:
                    t._remotly_push()
        if self.direction in ("both", "pull"):
            b._pull_changes()
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": _("Remotly sync complete"), "type": "success", "sticky": False,
                           "message": _("Projects and tasks synchronised.")}}
