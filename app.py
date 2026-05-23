from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, jsonify
from config import get_config
from isel.utils.image import ImageDecodeError


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

    @app.cli.command('auto-checkout')
    def _cli_auto_checkout():
        from isel.services.attendance import auto_checkout_all
        auto_checkout_all()

    @app.get('/')
    def index():
        return render_template('index.html')

    return app
