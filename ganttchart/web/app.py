import os

import flask
from werkzeug.routing import BaseConverter

from .. import database
from ..models import Account, Project, Session as SqlSession, Task
from . import forms


app = flask.Flask('ganttchart.web')
app.secret_key = os.environ['GANTT_CHART_SECRET_KEY']


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
        flask.g.account = account


@app.teardown_request
def remove_session(*args, **kwargs):
    SqlSession.remove()


@app.route('/')
def home():
    return flask.render_template('home.html')


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
        account = models.Account(form.email_address.data, form.password.data)
        flask.g.sql_session.add(account)
        flask.g.sql_session.commit()

    return flask.render_template('account/signup.html', form=form)


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    del flask.session['account_id']
    return flask.redirect(flask.url_for('.home'))


@app.route('/projects')
def projects():
    projects = list(flask.g.account.projects)
    return flask.render_template('projects/index.html', projects=projects)


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
    return flask.render_template('projects/view.html', project=project)


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
