from flask import Blueprint, render_template, request, redirect, url_for, session, flash

user_login_bp = Blueprint("user_login", __name__)

# Hardcoded user credentials for demonstration
USERNAME = 'user1'
PASSWORD = 'password'

@user_login_bp.route('/user_login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        # Retrieve form data
        username = request.form['username']
        password = request.form['password']
        
        # Check credentials
        if username == USERNAME and password == PASSWORD:
            # Store username in session and redirect to welcome
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('user_load_db.index'))
        else:
            flash('Invalid username or password!', 'danger')
            return redirect(url_for('user_login.user_login'))
    
    # Display login page for GET requests
    # return render_template('login.html')
    return render_template('user_login_center.html')

@user_login_bp.route('/logout')
def logout():
    # Clear the session and redirect to login
    session.pop('username', None)
    flash('Logged out successfully!', 'info')
    return redirect(url_for('user_login.user_login'))
