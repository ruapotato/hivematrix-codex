import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# --- App Initialization ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_secure_random_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///./nexus_brainhair.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Database Models ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    permission_level = db.Column(db.String(50), nullable=False, default='user') # e.g., 'user', 'admin'
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    location = db.Column(db.String(200))
    primary_contact_name = db.Column(db.String(150))
    primary_contact_email = db.Column(db.String(150))
    primary_contact_phone = db.Column(db.String(50))
    users = db.relationship('User', backref='company', lazy=True)

# --- User Loader for Flask-Login ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Decorators for Permissions ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.permission_level != 'admin':
            flash("You do not have permission to access this page.", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# --- Web Interface Routes ---

@app.route('/')
@login_required
def dashboard():
    companies = Company.query.all()
    users = User.query.all()
    return render_template('dashboard.html', companies=companies, users=users)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/add_user', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        company_id = request.form['company_id']
        permission_level = request.form.get('permission_level', 'user')

        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
        elif User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
        else:
            new_user = User(
                username=username,
                email=email,
                company_id=company_id,
                permission_level=permission_level
            )
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash('User created successfully!', 'success')
            return redirect(url_for('dashboard'))

    companies = Company.query.all()
    return render_template('add_user.html', companies=companies)


@app.route('/add_company', methods=['GET', 'POST'])
@login_required
@admin_required
def add_company():
    if request.method == 'POST':
        name = request.form['name']
        location = request.form['location']
        contact_name = request.form['primary_contact_name']
        contact_email = request.form['primary_contact_email']
        contact_phone = request.form['primary_contact_phone']

        if Company.query.filter_by(name=name).first():
            flash('Company name already exists.', 'danger')
        else:
            new_company = Company(
                name=name,
                location=location,
                primary_contact_name=contact_name,
                primary_contact_email=contact_email,
                primary_contact_phone=contact_phone
            )
            db.session.add(new_company)
            db.session.commit()
            flash('Company added successfully!', 'success')
            return redirect(url_for('dashboard'))
    return render_template('add_company.html')

# --- API Routes ---

@app.route('/api/companies', methods=['GET'])
def get_companies():
    companies = Company.query.all()
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'location': c.location,
        'primary_contact_name': c.primary_contact_name,
        'primary_contact_email': c.primary_contact_email,
        'primary_contact_phone': c.primary_contact_phone
    } for c in companies])

@app.route('/api/companies/<int:company_id>', methods=['GET'])
def get_company(company_id):
    company = Company.query.get_or_404(company_id)
    return jsonify({
        'id': company.id,
        'name': company.name,
        'location': company.location,
        'primary_contact_name': company.primary_contact_name,
        'primary_contact_email': company.primary_contact_email,
        'primary_contact_phone': company.primary_contact_phone
    })

@app.route('/api/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'email': u.email,
        'company_id': u.company_id,
        'permission_level': u.permission_level
    } for u in users])

@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'company_id': user.company_id,
        'permission_level': user.permission_level
    })

@app.route('/api/companies/<int:company_id>/users', methods=['GET'])
def get_users_for_company(company_id):
    company = Company.query.get_or_404(company_id)
    users = company.users
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'email': u.email,
        'permission_level': u.permission_level
    } for u in users])


if __name__ == '__main__':
    app.run(debug=True)
