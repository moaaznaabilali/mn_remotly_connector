# -*- coding: utf-8 -*-
{
    "name": "Remotly Connector | Two-Way Project & Task Sync",
    "version": "19.0.1.0.0",
    "category": "Project",
    "summary": "Two-way sync between Odoo Project and Remotly: projects, tasks, "
               "stages↔columns, assignees & users, comments, time and labels. "
               "Secure API-key auth. Real-time push + scheduled pull.",
    "description": """
Remotly Connector for Odoo
==========================
Keep Odoo Project and Remotly in perfect sync — both ways.

* **Projects** → Remotly projects (auto board + columns).
* **Tasks** → Remotly tasks, with priority and due date.
* **Stages ↔ Columns** — Odoo stages map to Remotly board columns by name
  (missing columns are created automatically).
* **Users / assignees** — Odoo users are linked to Remotly users by email and
  set as project members and task assignees.
* **Comments, time and labels** — kept in sync.
* **Two-way** — push on write (real-time) and pull changes on a schedule.
* **Secure** — connects with a Remotly API key (no password stored).

Free and open source (LGPL-3).
    """,
    "author": "Moaz Nabil",
    "website": "https://github.com/moaaznaabilali",
    "support": "moaaznaabilali@gmail.com",
    "license": "LGPL-3",
    "depends": ["base", "mail", "project"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/cron.xml",
        "views/remotly_backend_views.xml",
        "views/project_views.xml",
        "wizard/remotly_sync_wizard_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "auto_install": False,
}
