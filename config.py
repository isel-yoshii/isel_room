from __future__ import annotations
import os


class Config:
    # NOTE: DATABASE_URL deliberately does not live here. isel/db/__init__.py
    # builds the engine from the environment at import time, before any config
    # object exists, so a value set here could never take effect — set the
    # DATABASE_URL env var instead.
    SECRET_KEY: str = os.getenv('FLASK_SECRET_KEY', 'dev-secret-change-me')
    ADMIN_PIN: str = os.getenv('ADMIN_PIN', '')
    LOW_CONFIDENCE_THRESHOLD: float = float(os.getenv('LOW_CONFIDENCE_THRESHOLD', '0.40'))

    # Face matching knobs. Cameras, lighting and lenses differ between rooms,
    # so these are tunable without a code change. Lower = stricter.
    #   AUTH_THRESHOLD  max cosine distance to call it a match at all
    #   MATCH_MARGIN    how much closer the winner must be than the runner-up
    #                   identity; 0 disables the ambiguity check
    #   DETECT_CONFIDENCE  min RetinaFace confidence before an embedding is used
    FACE_AUTH_THRESHOLD: float    = float(os.getenv('FACE_AUTH_THRESHOLD', '0.55'))
    FACE_MATCH_MARGIN: float      = float(os.getenv('FACE_MATCH_MARGIN', '0.10'))
    FACE_DETECT_CONFIDENCE: float = float(os.getenv('FACE_DETECT_CONFIDENCE', '0.90'))
    DAY_RESET_HOUR: int = int(os.getenv('DAY_RESET_HOUR', '22'))

    # Slack integration. Required in production; in dev these can be empty and
    # the integration silently disables itself (see isel/integrations/slack.py).
    SLACK_BOT_TOKEN: str = os.getenv('SLACK_BOT_TOKEN', '')
    SLACK_APP_TOKEN: str = os.getenv('SLACK_APP_TOKEN', '')
    SLACK_CHANNEL: str   = os.getenv('SLACK_CHANNEL', '#a-lab-status')

    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = 'Lax'
    SESSION_COOKIE_SECURE: bool = False


class DevConfig(Config):
    DEBUG: bool = True


class ProdConfig(Config):
    DEBUG: bool = False
    SESSION_COOKIE_SECURE: bool = True

    def __init__(self) -> None:
        if not self.SECRET_KEY or self.SECRET_KEY == 'dev-secret-change-me':
            raise RuntimeError(
                'FLASK_SECRET_KEY must be set to a strong random value in production. '
                'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        if not self.ADMIN_PIN:
            raise RuntimeError('ADMIN_PIN must be set in production.')
        if not self.SLACK_BOT_TOKEN:
            raise RuntimeError('SLACK_BOT_TOKEN must be set in production.')
        if not self.SLACK_APP_TOKEN:
            raise RuntimeError(
                'SLACK_APP_TOKEN must be set in production. '
                'Required for Socket Mode (slash commands, real-time events).'
            )


class TestConfig(Config):
    TESTING: bool = True
    ADMIN_PIN: str = 'test-pin'
    SECRET_KEY: str = 'test-secret'
    LOW_CONFIDENCE_THRESHOLD: float = 0.40
    DAY_RESET_HOUR: int = 22
    # Slack stays disabled under tests (no tokens, no network).
    SLACK_BOT_TOKEN: str = ''
    SLACK_APP_TOKEN: str = ''
    SLACK_CHANNEL: str   = '#test-channel'


_configs: dict[str, type[Config]] = {
    'dev': DevConfig,
    'prod': ProdConfig,
    'test': TestConfig,
}


def get_config(name: str = 'dev') -> Config:
    return _configs.get(name, DevConfig)()
