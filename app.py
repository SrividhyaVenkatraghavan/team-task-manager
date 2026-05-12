import os
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Project, Task
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///taskmanager.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -------------------- AUTH ROUTES --------------------

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already exists!', 'danger')
            return redirect(url_for('signup'))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email,
                       password=hashed_password, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid email or password!', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# -------------------- DASHBOARD --------------------

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        projects = Project.query.all()
        tasks = Task.query.all()
    else:
        projects = Project.query.all()
        tasks = Task.query.filter_by(assigned_to=current_user.id).all()

    todo = [t for t in tasks if t.status == 'todo']
    in_progress = [t for t in tasks if t.status == 'in_progress']
    done = [t for t in tasks if t.status == 'done']
    overdue = [t for t in tasks if t.due_date and
               t.due_date < datetime.utcnow() and t.status != 'done']

    return render_template('dashboard.html',
                           projects=projects, tasks=tasks,
                           todo=todo, in_progress=in_progress,
                           done=done, overdue=overdue)

# -------------------- PROJECTS --------------------

@app.route('/projects')
@login_required
def projects():
    all_projects = Project.query.all()
    return render_template('projects.html', projects=all_projects)

@app.route('/projects/new', methods=['GET', 'POST'])
@login_required
def new_project():
    if current_user.role != 'admin':
        flash('Only admins can create projects!', 'danger')
        return redirect(url_for('projects'))
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        project = Project(name=name, description=description,
                         owner_id=current_user.id)
        db.session.add(project)
        db.session.commit()
        flash('Project created!', 'success')
        return redirect(url_for('projects'))
    return render_template('new_project.html')

@app.route('/projects/<int:project_id>/delete', methods=['POST'])
@login_required
def delete_project(project_id):
    if current_user.role != 'admin':
        flash('Only admins can delete projects!', 'danger')
        return redirect(url_for('projects'))
    project = Project.query.get_or_404(project_id)
    Task.query.filter_by(project_id=project_id).delete()
    db.session.delete(project)
    db.session.commit()
    flash('Project deleted!', 'success')
    return redirect(url_for('projects'))

# -------------------- TASKS --------------------

@app.route('/tasks')
@login_required
def tasks():
    if current_user.role == 'admin':
        all_tasks = Task.query.all()
    else:
        all_tasks = Task.query.filter_by(assigned_to=current_user.id).all()
    users = User.query.all()
    projects = Project.query.all()
    return render_template('tasks.html', tasks=all_tasks,
                           users=users, projects=projects)

@app.route('/tasks/new', methods=['GET', 'POST'])
@login_required
def new_task():
    if current_user.role != 'admin':
        flash('Only admins can create tasks!', 'danger')
        return redirect(url_for('tasks'))
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        project_id = request.form['project_id']
        assigned_to = request.form['assigned_to']
        due_date_str = request.form['due_date']
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d') if due_date_str else None
        task = Task(title=title, description=description,
                   project_id=project_id, assigned_to=assigned_to,
                   due_date=due_date)
        db.session.add(task)
        db.session.commit()
        flash('Task created!', 'success')
        return redirect(url_for('tasks'))
    users = User.query.all()
    projects = Project.query.all()
    return render_template('new_task.html', users=users, projects=projects)

@app.route('/tasks/<int:task_id>/update', methods=['POST'])
@login_required
def update_task(task_id):
    task = Task.query.get_or_404(task_id)
    if current_user.role != 'admin' and task.assigned_to != current_user.id:
        flash('Access denied!', 'danger')
        return redirect(url_for('tasks'))
    task.status = request.form['status']
    db.session.commit()
    flash('Task updated!', 'success')
    return redirect(url_for('tasks'))

@app.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    if current_user.role != 'admin':
        flash('Only admins can delete tasks!', 'danger')
        return redirect(url_for('tasks'))
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted!', 'success')
    return redirect(url_for('tasks'))

# -------------------- RUN --------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)