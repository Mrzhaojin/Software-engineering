import os
import secrets

from flask import Flask

from . import db
from .routes import bp


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("CAMPUS_EVENT_SECRET_KEY") or secrets.token_hex(32),
        DATABASE=os.path.join(app.instance_path, "campusevent.db"),
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    app.register_blueprint(bp)
    db.init_app(app)
    return app