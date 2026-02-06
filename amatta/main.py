# main.py
import threading
from flask import Flask, request, jsonify
from web.ad_login import ad_login_bp
from web.ad_load_db import ad_load_db_bp
from web.ad_detect import ad_detect_bp
from web.user_load_db import user_load_db_bp
#from web.user_login import user_login_bp
from web.lost_report import lost_report_bp
from web.guide_start import guide_start_bp
from web.search_start import search_start_bp 
# from web.found_item_listener import main


BASE_DIR = "/home/rokey/Desktop/amatta"   # 너 프로젝트 루트

def create_app():
    app = Flask(
        __name__,
        template_folder="/home/rokey/Desktop/amatta/template",
        static_folder="/home/rokey/Desktop/amatta/static",
        static_url_path="/static"
    )
    app.secret_key = "amatta"   # data 보호, 쿠키 수정 불가

    #app.register_blueprint(user_login_bp) # qr찍자마자 load_db 보이기
    app.register_blueprint(user_load_db_bp)     # /user_load, /filter
    app.register_blueprint(lost_report_bp)      # /lost_report(get, post), 
    app.register_blueprint(guide_start_bp)      # /guide_start, /api/publish_guidance
    app.register_blueprint(search_start_bp) 
                                                
    app.register_blueprint(ad_login_bp)         # /ad_login(get,post), /logout
    app.register_blueprint(ad_load_db_bp)       # /ad_load_db
    app.register_blueprint(ad_detect_bp)        # /ad_detect

    return app


if __name__ == "__main__":
    app = create_app()
    # threading.Thread(target=main, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=True)  # 5000port에서 열림
