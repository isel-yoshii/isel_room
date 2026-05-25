from __future__ import annotations
from flask import Flask


def register_blueprints(app: Flask) -> None:
    from isel.api import auth, attendance, users, stats, admin
    for mod in (auth, attendance, users, stats, admin):
        app.register_blueprint(mod.bp)
