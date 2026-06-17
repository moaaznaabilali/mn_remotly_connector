# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectTaskType(models.Model):
    _inherit = "project.task.type"

    # Odoo stages map to Remotly board columns by name. This optional override lets the
    # user pin a different Remotly column name than the stage name.
    remotly_column_name = fields.Char(string="Remotly column name",
                                      help="Leave empty to use the stage name as the column name.")

    def _remotly_name(self):
        self.ensure_one()
        return self.remotly_column_name or self.name
