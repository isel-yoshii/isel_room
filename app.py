from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template
from config import get_config


def create_app(config_name: str = 'dev') -> Flask:
    cfg = get_config(config_name)
    app = Flask(__name__, template_folder='ui', static_folder='ui', static_url_path='/ui')
    app.config.from_object(cfg)

    from isel.db import init_db
    init_db()

    # FaceEngine is stateful (embedding cache) — create once per app instance.
    from core.face_engine import FaceEngine

    class _EmbeddingAdapter:
        def get_all_embeddings(self) -> dict:
            from isel.services.users import get_all_embeddings
            return get_all_embeddings()

    app.config['FACE_ENGINE'] = FaceEngine(_EmbeddingAdapter())

    from isel.api import register_blueprints
    register_blueprints(app)

    @app.get('/')
    def index():
        return render_template('index.html')

    return app
