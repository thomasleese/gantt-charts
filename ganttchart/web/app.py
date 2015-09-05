import logging
import os

import flask

from .. import database
from ..chart import Chart
from ..models import Account, Project, Session as SqlSession, Task, \
    TaskDependency
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
        return flask.render_template('welcome.html')


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
        account = Account(form.email_address.data, form.password.data)
        flask.g.sql_session.add(account)
        flask.g.sql_session.commit()

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
    return flask.render_template('projects/view.html', project=project)


@app.route('/projects/<int:project_id>/chart')
def view_gantt_chart(project_id):
    project = flask.g.sql_session.query(Project).get(project_id)
    chart = Chart(project)
    return flask.render_template('projects/chart.html', project=project,
                                 chart=chart)


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
