# main.py
from flask import Flask, render_template
from web.ad_load_db import load_item, load_item_lost, DB_PATH
from web.ad_login import ad_login_bp
from web.ad_load_db import ad_load_db_bp
from web.ad_detect import ad_detect_bp
from web.user_load_db import user_load_db_bp
from web.user_login import user_login_bp

def create_app():
    app = Flask(
        __name__,
        template_folder="/home/rokey/Desktop/amatta/template",
        static_folder=None,
    )

    app.secret_key = "amatta"

    app.register_blueprint(ad_login_bp)         # /, /login, /welcome, /logout
    app.register_blueprint(ad_load_db_bp)   # /ad_load_db
    app.register_blueprint(ad_detect_bp)    # /ad_detect
    app.register_blueprint(user_load_db_bp)
    app.register_blueprint(user_login_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=True)