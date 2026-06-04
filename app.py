from __future__ import annotations
import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, jsonify
from config import get_config
from isel.utils import ImageDecodeError


def create_app(config_name: str = 'dev') -> Flask:
    cfg = get_config(config_name)
    app = Flask(__name__, template_folder='ui', static_folder='ui', static_url_path='/ui')
    app.config.from_object(cfg)
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8 MB request cap

    @app.errorhandler(ImageDecodeError)
    def _image_decode_error(err: ImageDecodeError):
        return jsonify({'matched': False, 'success': False, 'message': str(err)}), 400

    from isel.db import init_db
    init_db()

    # FaceEngine is stateful — create once per app instance.
    from isel.face_engine import FaceEngine
    from isel.services.users import get_all_embeddings
    app.config['FACE_ENGINE'] = FaceEngine(get_all_embeddings)

    from isel.api import register_blueprints
    register_blueprints(app)

    # Slack: start the bot client (and Socket Mode listener if both tokens
    # are present). In dev with Werkzeug's auto-reloader the parent process
    # spawns a child that re-runs create_app; only let the child start the
    # Socket Mode thread, otherwise we'd double-connect.
    _in_werkzeug_reloader_parent = (
        app.config.get('DEBUG') and os.environ.get('WERKZEUG_RUN_MAIN') != 'true'
    )
    if not _in_werkzeug_reloader_parent and not app.config.get('TESTING'):
        from isel.integrations.slack import init as init_slack
        init_slack(
            bot_token=app.config.get('SLACK_BOT_TOKEN', ''),
            app_token=app.config.get('SLACK_APP_TOKEN', ''),
            channel  =app.config.get('SLACK_CHANNEL', '#a-lab-status'),
        )

    # Auto-checkout scheduler: fires in-app at DAY_RESET_HOUR:00 (Asia/Tokyo).
    # Reuses the Werkzeug-reloader guard above so it doesn't double-start in dev,
    # and skips under tests. If gunicorn ever runs >1 worker, set ENABLE_SCHEDULER=0
    # on the extras so only one process schedules the job.
    if (
        not _in_werkzeug_reloader_parent
        and not app.config.get('TESTING')
        and os.environ.get('ENABLE_SCHEDULER', '1') != '0'
    ):
        from isel.jobs.scheduler import start as start_scheduler
        start_scheduler(app.config['DAY_RESET_HOUR'])

    @app.cli.command('auto-checkout')
    def _cli_auto_checkout():
        from isel.services.attendance import auto_checkout_all
        auto_checkout_all()

    @app.get('/')
    def index():
        return render_template('index.html')

    return app
