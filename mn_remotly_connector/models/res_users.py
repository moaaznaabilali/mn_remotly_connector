# -*- coding: utf-8 -*-
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    remotly_user_id = fields.Char(string="Remotly User ID", copy=False)
    remotly_backend_id = fields.Many2one("remotly.backend", copy=False)
