from flask import Blueprint, render_template, request, redirect, url_for, session, flash

ad_login_bp = Blueprint("ad_login", __name__)

# admin 하드 코딩
USERNAME = 'admin'
PASSWORD = 'admin'

# 관리자 로그인 페이지 처리 및 폼 데이터 검증 라우트
@ad_login_bp.route('/ad_login', methods=['GET', 'POST'])
def ad_login():
    if request.method == 'POST':
        # Retrieve form data
        username = request.form['username']
        password = request.form['password']
        
        # Check credentials
        if username == USERNAME and password == PASSWORD:
            # Store username in session and redirect to welcome
            session['username'] = username
            flash('Login successful!', 'success')
            # 로그인 성공 후 관리자용 DB 조회 페이지(ad_load_db)로 이동
            return redirect(url_for('ad_load_db.ad_load_db'))
        else:
            # 불일치할 경우: 에러 메시지 출력 후 다시 로그인 페이지로 리다이렉트
            flash('Invalid username or password!', 'danger')
            return redirect(url_for('ad_login.ad_login'))
    
    # Display login page for GET requests
    # return render_template('login.html')
    return render_template('ad_login_center.html')

@ad_login_bp.route('/logout')
def logout():
    # Clear the session and redirect to login
    session.pop('username', None)
    flash('Logged out successfully!', 'info')
    return redirect(url_for('ad_load_db.ad_load_db'))
