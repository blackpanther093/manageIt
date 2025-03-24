# from flask import redirect, url_for, session
# from authlib.integrations.flask_client import OAuth
# from db import get_db_connection
# from routes import app

# oauth = OAuth(app)

# google = oauth.register(
#     name='google',
#     client_id=app.config['GOOGLE_CLIENT_ID'],
#     client_secret=app.config['GOOGLE_CLIENT_SECRET'],
#     access_token_url='https://oauth2.googleapis.com/token',
#     authorize_url='https://accounts.google.com/o/oauth2/auth',
#     client_kwargs={'scope': 'openid email profile'}
# )

# @app.route('/login')
# def login():
#     redirect_uri = url_for('authorize', _external=True)
#     return google.authorize_redirect(redirect_uri)

# @app.route('/authorize')
# def authorize():
#     token = google.authorize_access_token()
#     session['token'] = token
#     user_info = google.get('https://www.googleapis.com/oauth2/v2/userinfo').json()
#     user_email = user_info['email']
#     user_name = user_info.get('name', 'Unknown')
#     connection = get_db_connection()
#     cursor = connection.cursor()
#     cursor.execute("SELECT * FROM students WHERE email = %s", (user_email,))
#     user = cursor.fetchone()
#     if not user:
#         cursor.execute("INSERT INTO students (name, email) VALUES (%s, %s)", (user_name, user_email))
#         connection.commit()
#     cursor.close()
#     connection.close()
#     return f"Welcome, {user_name} ({user_email})!"
