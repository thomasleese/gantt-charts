import datetime
import logging
import os

import flask
import sqlalchemy

from .. import database
from ..chart import Chart
from ..models import generate_key, AccessLevel, Account, AccountEmailAddress, \
    Project, ProjectCalendarHoliday, ProjectEntry, ProjectEntryDependency, \
    ProjectEntryMember, ProjectEntryType, ProjectEntryResource, \
    ProjectMember, ProjectResource, ProjectStar, Session as SqlSession
from . import errors, forms, routes


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


@app.after_request
def configure_session(response):
    if 'account' in flask.g:
        if 'CSRF-Token' not in flask.request.cookies:
            token = generate_key()
            response.set_cookie('CSRF-Token', token, httponly=False)
    return response


@app.teardown_request
def remove_session(*args, **kwargs):
    SqlSession.remove()


def get_project_or_404(project_id):
    return flask.g.sql_session.query(Project) \
        .filter(Project.id == project_id).one()


def get_project_member_or_404(member_id):
    return flask.g.sql_session.query(ProjectMember) \
        .filter(ProjectMember.id == member_id).one()


def get_project_resource_or_404(resource_id):
    return flask.g.sql_session.query(ProjectResource) \
        .filter(ProjectResource.id == resource_id).one()


def get_project_member_or_403(project):
    member = project.get_member(flask.g.account)
    if member is None:
        raise errors.NotAuthenticated()
    return member


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
    project = get_project_or_404(project_id)
    account_member = get_project_member_or_403(project)

    if not account_member.access_level.can_view:
        raise errors.MissingPermission('can_view')

    return flask.render_template('projects/view.html', project=project)


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


@app.route('/account/reset', methods=['GET', 'POST'])
@app.route('/account/reset/<int:account_id>/<reset_password_key>', methods=['GET', 'POST'])
def account_reset(account_id=None, reset_password_key=None):
    if account_id is not None and reset_password_key is not None:
        account = flask.g.sql_session.query(Account) \
            .filter(Account.id == account_id) \
            .filter(Account.reset_password_key == reset_password_key) \
            .filter(Account.reset_password_key_expiration_date >= datetime.datetime.now()) \
            .one()

        form = forms.AccountReset2(flask.request.form)
        if flask.request.method == 'POST' and form.validate():
            account.password = form.new_password.data
            account.reset_password_key = None
            account.reset_password_key_expiration_date = None
            flask.g.sql_session.commit()

            flask.flash('Your password has been changed.', 'success')
            return flask.redirect(flask.url_for('.login'))

        return flask.render_template('account/reset.html', stage=2, form=form)
    else:
        form = forms.AccountReset1(flask.request.form)
        if flask.request.method == 'POST' and form.validate():
            account = form.email_address.record.account
            account.reset_password()
            flask.g.sql_session.commit()
            flask.flash('Password reset email sent.', 'success')
            return flask.redirect(flask.url_for('.account_reset'))
        return flask.render_template('account/reset.html', stage=1, form=form)


@app.route('/account/email-addresses/<int:id>/send-verify-email')
def account_send_verify_email(id):
    email_address = flask.g.sql_session.query(AccountEmailAddress).get(id)
    if email_address.account == flask.g.account:
        email_address.send_verify_email()
        flask.g.sql_session.commit()
        flask.flash('Email sent, please check your inbox.', 'info')
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


@app.route('/account/<int:account_id>/avatar')
def account_avatar(account_id):
    account = flask.g.sql_session.query(Account).get(account_id)
    if account is None:
        raise errors.NotFound()

    initials = account.initials

    hue = account_id % 360

    svg = flask.render_template('account/avatar.svg', hue=hue,
                                initials=initials)

    response = flask.make_response(svg)
    response.headers['Content-Type'] = 'image/svg+xml'
    return response


routes.register(app)
