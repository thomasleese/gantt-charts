import logging
import os

import flask
import sqlalchemy

from .. import database
from ..chart import Chart
from ..models import AccessLevel, Account, AccountEmailAddress, Project, \
    ProjectMember, ProjectStar, Session as SqlSession, Task, TaskDependency
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
        return flask.render_template('projects/index.html')
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
        project = Project(form.name.data, form.description.data,
                          flask.g.account)
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
    if email_address.account == flask.g.account:
        email_address.send_verify_email()
    return flask.redirect(flask.url_for('.account'))


@app.route('/account/email-addresses/<int:id>/primary')
def account_primary_email(id):
    email_address = flask.g.sql_session.query(AccountEmailAddress).get(id)
    if email_address.account == flask.g.account:
        flask.g.account.primary_email_address.primary = False
        email_address.primary = True
        flask.g.sql_session.commit()
    return flask.redirect(flask.url_for('.account'))


@app.route('/account/email-addresses/<int:id>/delete')
def account_delete_email(id):
    email_address = flask.g.sql_session.query(AccountEmailAddress).get(id)
    if email_address.account == flask.g.account:
        if flask.g.account.primary_email_address != email_address:
            flask.g.sql_session.delete(email_address)
            flask.g.sql_session.commit()
        else:
            flask.flash('You cannot delete your primary email address.', 'warning')
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


@app.route('/account/password', methods=['POST'])
def account_password():
    form = forms.ChangePassword(flask.request.form)
    if form.validate():
        flask.g.account.password = form.new_password.data
        flask.g.sql_session.commit()
        flask.flash('Password changed.', 'success')
    else:
        flask.flash('Old password incorrect.', 'danger')
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


def get_project_or_404(project_id):
    return flask.g.sql_session.query(Project) \
        .filter(Project.id == project_id).one()


def get_project_member_or_404(member_id):
    return flask.g.sql_session.query(ProjectMember) \
        .filter(ProjectMember.id == member_id).one()


def get_project_member_or_403(project):
    member = project.get_member(flask.g.account)
    if member is None or not member.access_level.can_view:
        return flask.abort(403)
    return member


@app.route('/api/projects/<int:project_id>')
def api_project(project_id):
    project = get_project_or_404(project_id)
    member = get_project_member_or_403(project)

    return flask.jsonify(project=project.as_json())


@app.route('/api/projects/<int:project_id>/tasks')
def api_project_tasks(project_id):
    project = get_project_or_404(project_id)
    member = get_project_member_or_403(project)

    tasks = [task.as_json() for task in project.tasks]
    return flask.jsonify(tasks=tasks)


@app.route('/api/projects/<int:project_id>/gantt-chart')
def api_project_gantt_chart(project_id):
    project = get_project_or_404(project_id)
    account_member = get_project_member_or_403(project)

    try:
        chart = Chart(project)
    except RuntimeError:
        return flask.abort(404)

    return flask.jsonify(gantt_chart=chart.as_json())


@app.route('/api/projects/<int:project_id>/members', methods=['GET', 'POST'])
def api_project_members(project_id):
    project = get_project_or_404(project_id)
    account_member = get_project_member_or_403(project)

    if flask.request.method == 'GET':
        members = [member.as_json() for member in project.members]
        return flask.jsonify(members=members)
    elif flask.request.method == 'POST':
        if not account_member.access_level.can_administrate:
            return flask.abort(403)

        form = forms.ApiAddProjectMember.from_json(flask.request.json)
        if form.validate():
            members = project.members
            member = ProjectMember(form.email_address.record.account,
                                   AccessLevel[form.access_level.data])
            members.append(member)
            try:
                flask.g.sql_session.commit()
            except sqlalchemy.orm.exc.FlushError:
                return flask.abort(409)
            return '', 201
        else:
            return flask.abort(400)


@app.route('/api/projects/<int:project_id>/members/<int:account_id>', methods=['DELETE'])
def api_project_member(project_id, account_id):
    project = get_project_or_404(project_id)
    account_member = get_project_member_or_403(project)
    if not account_member.access_level.can_administrate:
        return flask.abort(403)

    target_member = project.get_member(account_id)
    if target_member is None:
        return flask.abort(404)

    if target_member.access_level.owner:
        return flask.abort(405)

    flask.g.sql_session.delete(target_member)
    flask.g.sql_session.commit()
    return '', 204
