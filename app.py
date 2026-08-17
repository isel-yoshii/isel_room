from __future__ import annotations
import logging
import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, jsonify, request
from werkzeug.exceptions import HTTPException
from config import get_config
from isel.utils import ApiError, ImageDecodeError


def create_app(config_name: str = 'dev') -> Flask:
    # Without this the diagnostics below are invisible: nothing configures the
    # root logger under gunicorn, so INFO records from isel.* are dropped and
    # only WARNING+ reaches stderr via logging's last-resort handler. The face
    # matcher and the auto-checkout job both report at INFO.
    _level = os.getenv('LOG_LEVEL', 'INFO').upper()
    logging.basicConfig(
        level=_level,
        format='%(asctime)s %(levelname)-8s %(name)s %(message)s',
    )
    logging.getLogger('isel').setLevel(_level)

    cfg = get_config(config_name)
    app = Flask(__name__, template_folder='ui', static_folder='ui', static_url_path='/ui')
    app.config.from_object(cfg)
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8 MB request cap

    @app.errorhandler(ImageDecodeError)
    def _image_decode_error(err: ImageDecodeError):
        return jsonify({'matched': False, 'success': False, 'message': str(err)}), 400

    # Everything under /api/ answers in JSON, including when it fails. The UI's
    # fetch wrapper does `.then(r => r.json())` with no status check, so an HTML
    # error page makes it throw a parse error and show the user nothing at all.
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
        # An exception that reached here is a bug, not a bad request. Log the
        # traceback for us; tell the caller nothing that leaks internals.
        app.logger.exception('Unhandled error on %s %s', request.method, request.path)
        if not _is_api():
            raise err
        detail = f'{type(err).__name__}: {err}' if app.config.get('DEBUG') else 'Internal server error'
        return jsonify({'success': False, 'message': detail}), 500

    from isel.db import init_db
    init_db()

    # FaceEngine is stateful — create once per app instance.
    from isel.face_engine import FaceEngine
    from isel.services.users import get_all_embeddings
    app.config['FACE_ENGINE'] = FaceEngine(
        get_all_embeddings,
        auth_threshold=app.config['FACE_AUTH_THRESHOLD'],
        match_margin=app.config['FACE_MATCH_MARGIN'],
        detect_confidence=app.config['FACE_DETECT_CONFIDENCE'],
    )

    from isel.api import register_blueprints
    register_blueprints(app)

    _in_werkzeug_reloader_parent = (
        app.config.get('DEBUG') and os.environ.get('WERKZEUG_RUN_MAIN') != 'true'
    )

    # Auto-checkout scheduler: fires in-app at DAY_RESET_HOUR:00 (Asia/Tokyo).
    #
    # Every reason for NOT starting is logged at WARNING. Silence here was the
    # whole problem: a process that skipped the scheduler looked identical to
    # one that started it, so a nightly job that never ran was invisible.
    _forced = os.environ.get('ENABLE_SCHEDULER')     # None | '0' | '1'
    if app.config.get('TESTING'):
        _skip = 'TESTING'
    elif _forced == '0':
        _skip = 'ENABLE_SCHEDULER=0'
    elif _in_werkzeug_reloader_parent and _forced != '1':
        # This guard is only correct when the reloader is actually active.
        # `flask run --no-reload` never sets WERKZEUG_RUN_MAIN, so it would skip
        # there too — ENABLE_SCHEDULER=1 forces past it.
        _skip = ('werkzeug reloader parent (dev). If you started with --no-reload '
                 'the scheduler will NOT run here: set ENABLE_SCHEDULER=1 to force it.')
    else:
        _skip = None

    if _skip:
        app.logger.warning('Auto-checkout scheduler NOT started: %s', _skip)
    else:
        from isel.jobs.scheduler import start as start_scheduler
        start_scheduler(app.config['DAY_RESET_HOUR'])

    # Slack: started AFTER the scheduler, and never allowed to be fatal.
    #
    # slack_bolt's App() calls auth.test during construction, so a revoked or
    # rotated token raised BoltError straight out of create_app — which killed
    # the whole application, the nightly auto-checkout included. A chat
    # integration must not be able to take down attendance, least of all while
    # the lab is migrating off Slack.
    if not _in_werkzeug_reloader_parent and not app.config.get('TESTING'):
        try:
            from isel.integrations.slack import init as init_slack
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
        from isel.services.attendance import auto_checkout_all
        closed = auto_checkout_all()
        print(f'Auto-checkout complete: {closed} session(s) closed.')

    @app.cli.command('scheduler-status')
    def _cli_scheduler_status():
        """Print scheduler state. NOTE: this starts a fresh process, so it does
        NOT report the state of a running gunicorn worker — use
        GET /api/admin/scheduler for that."""
        from isel.jobs.scheduler import status
        print(status())

    @app.get('/')
    def index():
        return render_template('index.html')

    return app
