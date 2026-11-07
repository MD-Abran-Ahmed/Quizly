import os
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from authlib.integrations.flask_client import OAuth
from database import db, User

auth_bp = Blueprint('auth', __name__)
login_manager = LoginManager()
oauth = OAuth()

def init_auth(app):
    """Initialize login manager and OAuth with the Flask app."""
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login_page'
    login_manager.login_message = 'Please log in to access your Quizly dashboard.'
    login_manager.login_message_category = 'warning'

    # Register Google OAuth client
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')

    oauth.init_app(app)
    if client_id and client_secret:
        oauth.register(
            name='google',
            client_id=client_id,
            client_secret=client_secret,
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'}
        )

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --- PAGE ROUTES ---

@auth_bp.route('/login')
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard_page'))
    google_configured = bool(os.getenv('GOOGLE_CLIENT_ID') and os.getenv('GOOGLE_CLIENT_SECRET'))
    return render_template('login.html', google_configured=google_configured)


@auth_bp.route('/register')
def register_page():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard_page'))
    google_configured = bool(os.getenv('GOOGLE_CLIENT_ID') and os.getenv('GOOGLE_CLIENT_SECRET'))
    return render_template('register.html', google_configured=google_configured)


# --- GOOGLE OAUTH ROUTES ---

@auth_bp.route('/auth/google')
def google_login():
    """Initiate Google OAuth flow."""
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')

    if not client_id or not client_secret:
        flash(
            'Google OAuth is not configured yet. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your .env file, or sign in using email/password.',
            'warning'
        )
        return redirect(url_for('auth.login_page'))

    # Determine redirect URI: allow override via GOOGLE_REDIRECT_URI or BASE_URL for production
    # Default to 127.0.0.1 for local development so Google OAuth never sees private LAN IPs
    redirect_uri = os.getenv('GOOGLE_REDIRECT_URI')
    if not redirect_uri:
        base_url = os.getenv('BASE_URL') or os.getenv('APP_URL')
        if base_url:
            redirect_uri = f"{base_url.rstrip('/')}/auth/google/callback"
        else:
            redirect_uri = 'http://127.0.0.1:{}/auth/google/callback'.format(
                os.getenv('PORT', '5000')
            )
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route('/auth/google/callback')
def google_callback():
    """Handle callback from Google OAuth."""
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get('userinfo')
        if not user_info:
            user_info = oauth.google.userinfo()

        email = user_info.get('email')
        name = user_info.get('name') or email.split('@')[0]
        google_id = user_info.get('sub')
        avatar = user_info.get('picture')

        if not email:
            flash('Google sign in did not return an email address.', 'error')
            return redirect(url_for('auth.login_page'))

        # Check existing user by google_id or email
        user = User.query.filter((User.google_id == google_id) | (User.email == email)).first()

        if not user:
            # Create user on first login
            user = User(
                email=email,
                name=name,
                google_id=google_id,
                avatar_url=avatar
            )
            db.session.add(user)
            db.session.commit()
        else:
            # Update user info if needed
            if not user.google_id:
                user.google_id = google_id
            if avatar and not user.avatar_url:
                user.avatar_url = avatar
            db.session.commit()

        login_user(user, remember=True)
        flash(f'Welcome back, {user.name}!', 'success')
        return redirect(url_for('dashboard_page'))

    except Exception as e:
        flash(f'Google sign in error: {str(e)}', 'error')
        return redirect(url_for('auth.login_page'))


# --- EMAIL / PASSWORD AUTH API ---

@auth_bp.route('/api/auth/register', methods=['POST'])
def api_register():
    data = request.get_json(silent=True) or request.form
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not name or not email or not password:
        return jsonify({'success': False, 'message': 'All fields are required.'}), 400

    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters.'}), 400

    if '@' not in email or '.' not in email:
        return jsonify({'success': False, 'message': 'Invalid email address format.'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': 'An account with this email already exists.'}), 409

    user = User(name=name, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    login_user(user, remember=True)
    return jsonify({
        'success': True,
        'message': f'Account created! Welcome to Quizly, {user.name}.',
        'redirect': url_for('dashboard_page')
    })


@auth_bp.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json(silent=True) or request.form
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    remember = bool(data.get('remember', False))

    if not email or not password:
        return jsonify({'success': False, 'message': 'Email and password are required.'}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'success': False, 'message': 'Invalid email or password.'}), 401

    login_user(user, remember=remember)
    return jsonify({
        'success': True,
        'message': f'Welcome back, {user.name}!',
        'redirect': url_for('dashboard_page')
    })



@auth_bp.route('/logout')
def logout():
    """Safely log out the user, clear session & remember cookies, and redirect to login page."""
    logout_user()
    session.clear()
    flash('You have been safely signed out.', 'info')
    resp = redirect(url_for('auth.login_page'))
    resp.delete_cookie('remember_token')
    resp.delete_cookie('session')
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@auth_bp.route('/api/auth/logout', methods=['GET', 'POST'])
def api_logout():
    """API endpoint to log out the user and return JSON."""
    logout_user()
    session.clear()
    resp = jsonify({
        'success': True,
        'message': 'You have been safely signed out.',
        'redirect': url_for('auth.login_page')
    })
    resp.delete_cookie('remember_token')
    resp.delete_cookie('session')
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@auth_bp.route('/api/auth/me')
def current_user_info():
    if not current_user.is_authenticated:
        return jsonify({'authenticated': False}), 200
    return jsonify({
        'authenticated': True,
        'user': current_user.to_dict()
    })

