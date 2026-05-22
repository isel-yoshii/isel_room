from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()

from flask import Flask
from config import get_config


def create_app(config_name: str = 'dev') -> Flask:
    cfg = get_config(config_name)
    app = Flask(__name__, template_folder='ui', static_folder='ui', static_url_path='/ui')
    app.config.from_object(cfg)

    from isel.db import init_db
    init_db()

    return app
