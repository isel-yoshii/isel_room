from __future__ import annotations
import logging
import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, jsonify, request
from werkzeug.exceptions import HTTPException
from config import get_config
from backend.utils import ApiError, ImageDecodeError


def create_app(config_name: str = 'dev') -> Flask:
    # Without this, nothing configures the root logger under gunicorn and every
    # INFO record from backend.* is dropped — including the face matcher's and the
    # auto-checkout job's only diagnostics.
    _level = os.getenv('LOG_LEVEL', 'INFO').upper()
    logging.basicConfig(
        level=_level,
        format='%(asctime)s %(levelname)-8s %(name)s %(message)s',
    )
    logging.getLogger('backend').setLevel(_level)

    cfg = get_config(config_name)
    app = Flask(__name__, template_folder='frontend', static_folder='frontend', static_url_path='/frontend')
    app.config.from_object(cfg)
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024

    @app.errorhandler(ImageDecodeError)
    def _image_decode_error(err: ImageDecodeError):
        return jsonify({'matched': False, 'success': False, 'message': str(err)}), 400

    # /api/ must answer JSON even when it fails: the UI's fetch wrapper calls
    # r.json() with no status check, so an HTML error page shows the user nothing.
    def _is_api() -> bool:
        return request.path.startswith('/api/')

    @app.errorhandler(ApiError)
    def _api_error(err: ApiError):
        return jsonify({'success': False, 'message': str(err)}), err.status

    @app.errorhandler(HTTPException)
    def _http_error(err: HTTPException):
        if not _is_api():
            return err
        return jsonify({'success': False, 'message': err.description}), err.code

    @app.errorhandler(Exception)
    def _unhandled_error(err: Exception):
        app.logger.exception('Unhandled error on %s %s', request.method, request.path)
        if not _is_api():
            raise err
        detail = f'{type(err).__name__}: {err}' if app.config.get('DEBUG') else 'Internal server error'
        return jsonify({'success': False, 'message': detail}), 500

    from backend.db import init_db
    init_db()

    from backend.face_engine import FaceEngine
    from backend.services.users import get_all_embeddings
    app.config['FACE_ENGINE'] = FaceEngine(
        get_all_embeddings,
        auth_threshold=app.config['FACE_AUTH_THRESHOLD'],
        match_margin=app.config['FACE_MATCH_MARGIN'],
        detect_confidence=app.config['FACE_DETECT_CONFIDENCE'],
    )

    from backend.api import register_blueprints
    register_blueprints(app)

    _in_werkzeug_reloader_parent = (
        app.config.get('DEBUG') and os.environ.get('WERKZEUG_RUN_MAIN') != 'true'
    )

    # Auto-checkout scheduler: fires in-app at DAY_RESET_HOUR:00 (Asia/Tokyo).
    # Deliberately NOT guarded by _in_werkzeug_reloader_parent, unlike Slack —
    # that guard skipped the scheduler on every `flask run` and the 22:00
    # checkout silently never fired. Post-mortem: ISEL_ROOM_GUIDE.md §9.
    # Double-scheduling is harmless anyway; auto_checkout_all() is idempotent.
    # Every reason for NOT starting is logged at WARNING, because silence here
    # made a job that never ran look exactly like one that did.
    _forced = os.environ.get('ENABLE_SCHEDULER')
    if app.config.get('TESTING'):
        _skip = 'TESTING'
    elif _forced == '0':
        _skip = 'ENABLE_SCHEDULER=0'
    else:
        _skip = None

    if _skip:
        app.logger.warning('Auto-checkout scheduler NOT started: %s', _skip)
    else:
        from backend.jobs.scheduler import start as start_scheduler
        start_scheduler(app.config['DAY_RESET_HOUR'])

    # Started AFTER the scheduler and never allowed to be fatal: slack_bolt's
    # App() calls auth.test during construction, so a rotated token used to
    # raise straight out of create_app and take attendance down with it.
    if not _in_werkzeug_reloader_parent and not app.config.get('TESTING'):
        try:
            from backend.integrations.slack import init as init_slack
            init_slack(
                bot_token=app.config.get('SLACK_BOT_TOKEN', ''),
                app_token=app.config.get('SLACK_APP_TOKEN', ''),
                channel  =app.config.get('SLACK_CHANNEL', '#a-lab-status'),
            )
        except Exception:
            app.logger.exception(
                'Slack integration failed to start; continuing without it. '
                'Check-in, the dashboard and auto-checkout are unaffected.')

    @app.cli.command('auto-checkout')
    def _cli_auto_checkout():
        """Close everyone out now. Safe to run from OS cron as a safety net."""
        from backend.services.attendance import auto_checkout_all
        closed = auto_checkout_all()
        print(f'Auto-checkout complete: {closed} session(s) closed.')

    @app.cli.command('scheduler-status')
    def _cli_scheduler_status():
        """Print scheduler state. Starts a fresh process, so it does NOT report
        a running gunicorn worker — use GET /api/admin/scheduler for that."""
        from backend.jobs.scheduler import status
        print(status())

    @app.get('/')
    def index():
        return render_template('index.html')

    return app
