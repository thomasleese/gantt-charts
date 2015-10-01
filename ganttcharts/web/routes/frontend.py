"""
Routes for the front-end.
"""

import datetime
import functools

import cairocffi
cairocffi.install_as_pycairo()

import cairosvg
import flask
import sqlalchemy

from ganttcharts import database
from ganttcharts.chart import Chart, InvalidGanttChart
from ganttcharts.models import generate_key, AccessLevel, Account, \
    AccountEmailAddress, Project, ProjectCalendarHoliday, ProjectEntry, \
    ProjectEntryDependency, ProjectEntryMember, ProjectEntryType, \
    ProjectEntryResource, ProjectMember, ProjectResource, ProjectStar, \
    Session as SqlSession
from ganttcharts.web import errors, forms


blueprint = flask.Blueprint('frontend', __name__)


def get_project_or_404(project_id):
    try:
        return flask.g.sql_session.query(Project) \
            .filter(Project.id == project_id).one()
    except sqlalchemy.orm.exc.NoResultFound:
        raise errors.NotFound()


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


def login_required(func):
    @functools.wraps(func)
    def decorated_function(*args, **kwargs):
        if 'account' not in flask.g:
            return flask.redirect(flask.url_for('.login', next=flask.request.url))
        return func(*args, **kwargs)
    return decorated_function


@blueprint.route('/')
def home():
    if 'account' in flask.g:
        return flask.render_template('projects/index.html')
    else:
        return flask.render_template('welcome/index.html')


@blueprint.route('/login', methods=['GET', 'POST'])
def login():
    form = forms.LogIn(flask.request.form)
    if flask.request.method == 'POST' and form.validate():
        account = form.password.record.account
        flask.session['account_id'] = account.id
        if 'next' in flask.request.args:
            return flask.redirect(flask.request.args['next'])
        else:
            return flask.redirect(flask.url_for('.home'))

    return flask.render_template('account/login.html', form=form)


@blueprint.route('/signup', methods=['GET', 'POST'])
def signup():
    form = forms.SignUp(flask.request.form)
    if flask.request.method == 'POST' and form.validate():
        account = Account(form.display_name.data, form.email_address.data,
                          form.password.data)
        flask.g.sql_session.add(account)
        flask.g.sql_session.commit()
        return flask.redirect(flask.url_for('.login'))

    return flask.render_template('account/signup.html', form=form)


@blueprint.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    del flask.session['account_id']
    return flask.redirect(flask.url_for('.home'))


@blueprint.route('/projects/new', methods=['GET', 'POST'])
@login_required
def new_project():
    form = forms.CreateProject(flask.request.form)
    if flask.request.method == 'POST' and form.validate():
        project = Project(form.name.data, form.description.data,
                          flask.g.account)
        flask.g.sql_session.add(project)
        flask.g.sql_session.commit()
        return flask.redirect(flask.url_for('.view_project', project_id=project.id))
    return flask.render_template('projects/create.html', form=form)


@blueprint.route('/projects/<int:project_id>')
@login_required
def view_project(project_id):
    project = get_project_or_404(project_id)
    account_member = get_project_member_or_403(project)

    if not account_member.access_level.can_view:
        raise errors.MissingPermission('can_view')

    return flask.render_template('projects/view.html', project=project)


@blueprint.route('/projects/<int:project_id>/gantt-chart.<format>')
def project_gantt_chart(project_id, format):
    project = get_project_or_404(project_id)
    account_member = get_project_member_or_403(project)

    try:
        chart = Chart(project)
    except InvalidGanttChart:
        chart=None

    svg = flask.render_template('projects/gantt-chart.svg', chart=chart,
                                project=project,
                                today=datetime.datetime.utcnow())

    if format == 'svg':
        response = flask.make_response(svg)
        response.headers['Content-Type'] = 'image/svg+xml'
    elif format == 'pdf':
        pdf = cairosvg.svg2pdf(svg)

        response = flask.make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'

        filename = 'Gantt Chart for {}.pdf'.format(project.name)
        response.headers['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
    elif format == 'png':
        png = cairosvg.svg2png(svg)

        response = flask.make_response(png)
        response.headers['Content-Type'] = 'image/png'

        filename = 'Gantt Chart for {}.png'.format(project.name)
        response.headers['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
    else:
        raise errors.NotFound()

    return response


@blueprint.route('/projects/<int:project_id>/star')
@login_required
def star_project(project_id):
    # TODO check if they are a member
    star = ProjectStar(account=flask.g.account, project_id=project_id)
    flask.g.sql_session.add(star)
    flask.g.sql_session.commit()
    return flask.redirect(flask.url_for('.home'))


@blueprint.route('/projects/<int:project_id>/unstar')
@login_required
def unstar_project(project_id):
    star = flask.g.sql_session.query(ProjectStar) \
        .filter(ProjectStar.account == flask.g.account) \
        .filter(ProjectStar.project_id == project_id) \
        .one()
    flask.g.sql_session.delete(star)
    flask.g.sql_session.commit()
    return flask.redirect(flask.url_for('.home'))


@blueprint.route('/account')
@login_required
def account():
    return flask.render_template('account/index.html')


@blueprint.route('/account/email-addresses', methods=['POST'])
@login_required
def account_email_addresses():
    form = forms.EmailAddress(flask.request.form)
    if form.validate():
        email_address = AccountEmailAddress(form.email_address.data)
        flask.g.account.email_addresses.append(email_address)
        flask.g.sql_session.commit()
    else:
        flask.flash('Could not add email address.', 'warning')
    return flask.redirect(flask.url_for('.account'))


@blueprint.route('/account/reset', methods=['GET', 'POST'])
@blueprint.route('/account/reset/<int:account_id>/<reset_password_key>', methods=['GET', 'POST'])
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


@blueprint.route('/account/email-addresses/<int:id>/send-verify-email')
@login_required
def account_send_verify_email(id):
    email_address = flask.g.sql_session.query(AccountEmailAddress).get(id)
    if email_address.account == flask.g.account:
        email_address.send_verify_email()
        flask.g.sql_session.commit()
        flask.flash('Email sent, please check your inbox.', 'info')
    return flask.redirect(flask.url_for('.account'))


@blueprint.route('/account/email-addresses/<int:id>/primary')
@login_required
def account_primary_email(id):
    email_address = flask.g.sql_session.query(AccountEmailAddress).get(id)
    if email_address.account == flask.g.account:
        flask.g.account.primary_email_address.primary = False
        email_address.primary = True
        flask.g.sql_session.commit()
    return flask.redirect(flask.url_for('.account'))


@blueprint.route('/account/email-addresses/<int:id>/delete')
@login_required
def account_delete_email(id):
    email_address = flask.g.sql_session.query(AccountEmailAddress).get(id)
    if email_address.account == flask.g.account:
        if flask.g.account.primary_email_address != email_address:
            flask.g.sql_session.delete(email_address)
            flask.g.sql_session.commit()
        else:
            flask.flash('You cannot delete your primary email address.', 'warning')
    return flask.redirect(flask.url_for('.account'))


@blueprint.route('/account/email-addresses/<int:id>/verify/<key>')
@login_required
def account_verify_email(id, key):
    email_address = flask.g.sql_session.query(AccountEmailAddress) \
        .filter(AccountEmailAddress.id == id) \
        .filter(AccountEmailAddress.verify_key == key) \
        .one()
    email_address.verified = True
    flask.g.sql_session.commit()
    flask.flash('Email address verified.', 'success')
    return flask.redirect(flask.url_for('.account'))


@blueprint.route('/account/password', methods=['POST'])
@login_required
def account_password():
    form = forms.ChangePassword(flask.request.form)
    if form.validate():
        flask.g.account.password = form.new_password.data
        flask.g.sql_session.commit()
        flask.flash('Password changed.', 'success')
    else:
        flask.flash('Old password incorrect.', 'danger')
    return flask.redirect(flask.url_for('.account'))


@blueprint.route('/account/<int:account_id>/avatar')
@login_required
def account_avatar(account_id):
    account = flask.g.sql_session.query(Account).get(account_id)
    if account is None:
        raise errors.NotFound()

    svg = flask.render_template('account/avatar.svg', account=account)

    response = flask.make_response(svg)
    response.headers['Content-Type'] = 'image/svg+xml'
    return response


@blueprint.errorhandler(404)
def page_not_found(e):
    return flask.render_template('errors/404.html')
