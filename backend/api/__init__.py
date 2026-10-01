from __future__ import annotations
from flask import Flask


def register_blueprints(app: Flask) -> None:
    from backend.api import auth, attendance, users, stats, admin, presence
    for mod in (auth, attendance, users, stats, admin, presence):
        app.register_blueprint(mod.bp)
