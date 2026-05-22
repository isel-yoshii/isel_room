from __future__ import annotations
from flask import Flask


def register_blueprints(app: Flask) -> None:
    from isel.api.auth import bp as auth_bp
    from isel.api.checkin import bp as checkin_bp
    from isel.api.users import bp as users_bp
    from isel.api.sessions import bp as sessions_bp
    from isel.api.presence import bp as presence_bp
    from isel.api.stats import bp as stats_bp
    from isel.api.admin import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(checkin_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(presence_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(admin_bp)
