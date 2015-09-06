import logging
import os

import flask

from .. import database
from ..chart import Chart
from ..models import Account, AccountEmailAddress, Project, ProjectStar, \
    Session as SqlSession, Task, TaskDependency
from . import forms


app = flask.Flask('ganttchart.web')
app.secret_key = os.environ['GANTT_CHART_SECRET_KEY']


@app.before_first_request
def configure_logging():
    if not app.debug:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        app.logger.addHandler(stream_handler)


@app.before_first_request
def configure_database():
    app.sql_engine = database.get_sql_engine()
    app.sql_connection = database.get_sql_connection()


@app.before_request
def configure_session(*args, **kwargs):
    flask.g.sql_session = SqlSession()

    if 'account_id' in flask.session:
        account = flask.g.sql_session.query(Account) \
            .get(flask.session['account_id'])
        if account is not None:
            flask.g.account = account


@app.teardown_request
def remove_session(*args, **kwargs):
    SqlSession.remove()


@app.route('/')
def home():
    if 'account' in flask.g:
        projects = list(flask.g.account.projects)
        return flask.render_template('projects/index.html', projects=projects)
    else:
        return flask.render_template('welcome/index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = forms.LogIn(flask.request.form)
    if flask.request.method == 'POST' and form.validate():
        account = form.password.record.account
        flask.session['account_id'] = account.id
        return flask.redirect(flask.url_for('.home'))

    return flask.render_template('account/login.html', form=form)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = forms.SignUp(flask.request.form)
    if flask.request.method == 'POST' and form.validate():
        account = Account(form.display_name.data, form.email_address.data,
                          form.password.data)
        flask.g.sql_session.add(account)
        flask.g.sql_session.commit()
        return flask.redirect(flask.url_for('.login'))

    return flask.render_template('account/signup.html', form=form)


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    del flask.session['account_id']
    return flask.redirect(flask.url_for('.home'))


@app.route('/projects/new', methods=['GET', 'POST'])
def new_project():
    form = forms.CreateProject(flask.request.form)
    if flask.request.method == 'POST' and form.validate():
        project = Project(form.name.data, flask.g.account)
        flask.g.sql_session.add(project)
        flask.g.sql_session.commit()
        return flask.redirect(flask.url_for('.view_project', project_id=project.id))
    return flask.render_template('projects/create.html', form=form)


@app.route('/projects/<int:project_id>')
def view_project(project_id):
    project = flask.g.sql_session.query(Project).get(project_id)
    try:
        chart = Chart(project)
    except RuntimeError:
        chart = None
    return flask.render_template('projects/chart.html', project=project,
                                 chart=chart)


@app.route('/projects/<int:project_id>/star')
def star_project(project_id):
    # TODO check if they are a member
    star = ProjectStar(account=flask.g.account, project_id=project_id)
    flask.g.sql_session.add(star)
    flask.g.sql_session.commit()
    return flask.redirect(flask.url_for('.home'))


@app.route('/projects/<int:project_id>/unstar')
def unstar_project(project_id):
    star = flask.g.sql_session.query(ProjectStar) \
        .filter(ProjectStar.account == flask.g.account) \
        .filter(ProjectStar.project_id == project_id) \
        .one()
    flask.g.sql_session.delete(star)
    flask.g.sql_session.commit()
    return flask.redirect(flask.url_for('.home'))


@app.route('/projects/<int:project_id>/tasks')
def view_project_tasks(project_id):
    project = flask.g.sql_session.query(Project).get(project_id)
    return flask.render_template('projects/tasks.html', project=project)


@app.route('/projects/<int:project_id>/members')
def view_project_members(project_id):
    project = flask.g.sql_session.query(Project).get(project_id)
    return flask.render_template('projects/members.html', project=project)


@app.route('/tasks/new/<int:project_id>', methods=['GET', 'POST'])
def new_task(project_id):
    project = flask.g.sql_session.query(Project).get(project_id)

    form = forms.CreateTask(flask.request.form)
    if flask.request.method == 'POST' and form.validate():
        time_estimates = (form.optimistic_time_estimate.data * 60 * 60 * 24,
                          form.normal_time_estimate.data * 60 * 60 * 24,
                          form.pessimistic_time_estimate.data * 60 * 60 * 24)
        task = Task(form.name.data, form.description.data,
                    time_estimates, project)
        flask.g.sql_session.add(task)
        flask.g.sql_session.commit()
        return flask.redirect(flask.url_for('.view_project', project_id=project.id))
    return flask.render_template('tasks/create.html', form=form)


@app.route('/tasks/<int:task_id>', methods=['GET', 'POST'])
def view_task(task_id):
    task = flask.g.sql_session.query(Task).get(task_id)

    form = forms.AddTaskDependency(flask.request.form)
    form.dependency.choices = [(t.id, t.name) for t in task.project.tasks]
    if flask.request.method == 'POST' and form.validate():
        task.dependencies.append(TaskDependency(dependency_id=form.dependency.data))
        flask.g.sql_session.commit()
        return flask.redirect(flask.url_for('.view_project', project_id=task.project.id))

    return flask.render_template('tasks/view.html', task=task, form=form)


@app.route('/account')
def account():
    return flask.render_template('account/index.html')


@app.route('/account/email-addresses', methods=['POST'])
def account_email_addresses():
    form = forms.EmailAddress(flask.request.form)
    if form.validate():
        email_address = AccountEmailAddress(form.email_address.data)
        flask.g.account.email_addresses.append(email_address)
        flask.g.sql_session.commit()
    else:
        flask.flash('Could not add email address.', 'warning')
    return flask.redirect(flask.url_for('.account'))


@app.route('/account/email-addresses/<int:id>/send-verify-email')
def account_send_verify_email(id):
    email_address = flask.g.sql_session.query(AccountEmailAddress).get(id)
    email_address.send_verify_email()
    return flask.redirect(flask.url_for('.account'))


@app.route('/account/email-addresses/<int:id>/verify/<key>')
def account_verify_email(id, key):
    email_address = flask.g.sql_session.query(AccountEmailAddress) \
        .filter(AccountEmailAddress.id == id) \
        .filter(AccountEmailAddress.verify_key == key) \
        .one()
    email_address.verified = True
    flask.g.sql_session.commit()
    flask.flash('Email address verified.', 'success')
    return flask.redirect(flask.url_for('.account'))


@app.route('/api/account', methods=['PATCH'])
def api_change_account():
    form = forms.ApiChangeAccount.from_json(flask.request.json)
    if form.validate():
        flask.g.account.display_name = form.display_name.data
        flask.g.sql_session.commit()
        return flask.jsonify()
    else:
        return flask.jsonify(errors=form.errors), 400
