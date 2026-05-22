from __future__ import annotations
import os


class Config:
    SECRET_KEY: str = os.getenv('FLASK_SECRET_KEY', 'dev-secret-change-me')
    DATABASE_URL: str = os.getenv('DATABASE_URL', 'sqlite:///isel_room.db')
    ADMIN_PIN: str = os.getenv('ADMIN_PIN', '')
    LOW_CONFIDENCE_THRESHOLD: float = float(os.getenv('LOW_CONFIDENCE_THRESHOLD', '0.40'))
    DAY_RESET_HOUR: int = int(os.getenv('DAY_RESET_HOUR', '4'))

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


class TestConfig(Config):
    TESTING: bool = True
    DATABASE_URL: str = 'sqlite:///:memory:'
    ADMIN_PIN: str = 'test-pin'
    SECRET_KEY: str = 'test-secret'
    LOW_CONFIDENCE_THRESHOLD: float = 0.40
    DAY_RESET_HOUR: int = 4


_configs: dict[str, type[Config]] = {
    'dev': DevConfig,
    'prod': ProdConfig,
    'test': TestConfig,
}


def get_config(name: str = 'dev') -> Config:
    return _configs.get(name, DevConfig)()
