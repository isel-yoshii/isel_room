from __future__ import annotations
from flask import Flask


def register_blueprints(app: Flask) -> None:
    from isel.api import auth, checkin, users, sessions, presence, stats, admin
    for mod in (auth, checkin, users, sessions, presence, stats, admin):
        app.register_blueprint(mod.bp)
