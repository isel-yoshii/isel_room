from __future__ import annotations
import threading
from flask import Flask


def start_background_jobs(app: Flask) -> None:
    from isel.jobs.auto_checkout import start_checkout_thread, start_promotion_thread
    start_checkout_thread(app)
    start_promotion_thread(app)
