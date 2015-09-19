import datetime
import logging
import os

import flask
import sqlalchemy

from .. import database
from ..chart import Chart
from ..models import AccessLevel, Account, AccountEmailAddress, Project, \
    ProjectCalendarHoliday, ProjectEntry, ProjectEntryDependency, \
    ProjectEntryMember, ProjectEntryType, ProjectEntryResource, \
    ProjectMember, ProjectResource, ProjectStar, Session as SqlSession
from . import errors, forms


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


def get_project_resource_or_404(resource_id):
    return flask.g.sql_session.query(ProjectResource) \
        .filter(ProjectResource.id == resource_id).one()


def get_project_member_or_403(project):
    member = project.get_member(flask.g.account)
    if member is None:
        raise errors.NotAuthenticated()
    return member


@app.route('/api/projects/<int:project_id>')
def api_project(project_id):
    project = get_project_or_404(project_id)
    account_member = get_project_member_or_403(project)

    if not account_member.access_level.can_view:
        raise errors.MissingPermission('can_view')

    return flask.jsonify(project=project.as_json())


@app.route('/api/projects/<int:project_id>/calendar', methods=['GET', 'PATCH'])
def api_project_calendar(project_id):
    project = get_project_or_404(project_id)
    account_member = get_project_member_or_403(project)

    if flask.request.method == 'GET':
        if not account_member.access_level.can_view:
            raise errors.MissingPermission('can_view')

        return flask.jsonify(calendar=project.calendar.as_json())
    elif flask.request.method == 'PATCH':
        if not account_member.access_level.can_administrate:
            raise errors.MissingPermission('can_administrate')

        form = forms.ApiChangeProjectCalendar.from_json(flask.request.json)
        if form.validate():
            days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday',
                    'saturday', 'sunday']
            for day in days:
                if getattr(form.working_week, day).raw_data:
                    value = getattr(form.working_week, day).data
                    setattr(project.calendar, 'works_on_' + day, value)

            if form.working_day.start.raw_data:
                project.calendar.work_starts_at = datetime.datetime.strptime(form.working_day.start.data, '%H:%M').time()

            if form.working_day.end.raw_data:
                project.calendar.work_ends_at = datetime.datetime.strptime(form.working_day.end.data, '%H:%M').time()

            if form.start_date.raw_data:
                project.calendar.start_date = form.start_date.data

            flask.g.sql_session.commit()

            return '', 204
        else:
            raise errors.InvalidFormData(form)


@app.route('/api/projects/<int:project_id>/calendar/holidays', methods=['POST'])
def api_project_calendar_holidays(project_id):
    project = get_project_or_404(project_id)
    account_member = get_project_member_or_403(project)

    if not account_member.access_level.can_administrate:
        raise errors.MissingPermission('can_administrate')

    form = forms.ApiAddCalendarHoliday.from_json(flask.request.json)
    if form.validate():
        holidays = project.calendar.holidays
        holiday = ProjectCalendarHoliday(form.name.data, form.start.data,
                                         form.end.data)
        holidays.append(holiday)

        flask.g.sql_session.commit()

        return '', 201
    else:
        raise errors.InvalidFormData(form)


@app.route('/api/projects/<int:project_id>/calendar/holidays/<int:holiday_id>', methods=['DELETE'])
def api_project_calendar_holiday(project_id, holiday_id):
    project = get_project_or_404(project_id)
    account_member = get_project_member_or_403(project)
    if not account_member.access_level.can_administrate:
        raise errors.MissingPermission('can_administrate')

    target_holiday = flask.g.sql_session.query(ProjectCalendarHoliday) \
        .filter(ProjectCalendarHoliday.id == holiday_id).one()

    flask.g.sql_session.delete(target_holiday)
    flask.g.sql_session.commit()
    return '', 204


@app.route('/api/projects/<int:project_id>/entries', methods=['GET', 'POST'])
def api_project_entries(project_id):
    project = get_project_or_404(project_id)
    account_member = get_project_member_or_403(project)

    if flask.request.method == 'GET':
        if not account_member.access_level.can_view:
            raise errors.MissingPermission('can_view')

        entries = [entry.as_json() for entry in project.entries]
        return flask.jsonify(entries=entires)
    elif flask.request.method == 'POST':
        if not account_member.access_level.can_edit:
            raise errors.MissingPermission('can_edit')

        form = forms.ApiAddProjectEntry.from_json(flask.request.json)
        if form.validate():
            entry = ProjectEntry(form.name.data, form.description.data,
                                 ProjectEntryType[form.type.data],
                                 form.normal_time_estimate.data,
                                 form.pessimistic_time_estimate.data, project)

            flask.g.sql_session.add(entry)
            flask.g.sql_session.commit()

            return flask.jsonify(entry=entry.as_json()), 201
        else:
            raise errors.InvalidFormData(form)


@app.route('/api/projects/<int:project_id>/entries/<int:entry_id>', methods=['GET', 'PATCH', 'DELETE'])
def api_project_entry(project_id, entry_id):
    project = get_project_or_404(project_id)
    account_member = get_project_member_or_403(project)

    if not account_member.access_level.can_edit:
        raise errors.MissingPermission('can_edit')

    entry = flask.g.sql_session.query(ProjectEntry) \
        .filter(ProjectEntry.id == entry_id).one()
    if entry.project != project:
        raise errors.NotFound()

    if flask.request.method == 'GET':
        return flask.jsonify(entry=entry.as_json())
    elif flask.request.method == 'PATCH':
        form = forms.ApiChangeProjectEntry.from_json(flask.request.json)
        if form.validate():
            if form.name.raw_data:
                entry.name = form.name.data

            if form.description.raw_data:
                entry.description = form.description.data

            if form.type.raw_data:
                entry.type = ProjectEntryType[form.type.data]

            if form.normal_time_estimate.raw_data:
                entry.normal_time_estimate = form.normal_time_estimate.data

            if form.pessimistic_time_estimate.raw_data:
                entry.pessimistic_time_estimate = form.pessimistic_time_estimate.data

            flask.g.sql_session.commit()

            return '', 204
        else:
            raise errors.InvalidFormData(form)
    elif flask.request.method == 'DELETE':
        flask.g.sql_session.delete(entry)
        flask.g.sql_session.commit()

        return '', 204


@app.route('/api/projects/<int:project_id>/entries/<int:entry_id>/resources/<int:resource_id>', methods=['PUT', 'DELETE'])
def api_project_entry_resource(project_id, entry_id, resource_id):
    project = get_project_or_404(project_id)
    account_member = get_project_member_or_403(project)

    if not account_member.access_level.can_edit:
        raise errors.MissingPermission('can_edit')

    if flask.request.method == 'PUT':
        form = forms.ApiAddProjectEntryResource.from_json(flask.request.json)
        if form.validate():
            entry_resource = ProjectEntryResource(entry_id=entry_id,
                                                  resource_id=resource_id,
                                                  amount=form.amount.data)

            flask.g.sql_session.add(entry_resource)
            flask.g.sql_session.commit()

            return '', 201
        else:
            raise errors.InvalidFormData(form)
    elif flask.request.method == 'DELETE':
        try:
            entry_resource = flask.g.sql_session.query(ProjectEntryResource) \
                .filter(ProjectEntryResource.entry_id == entry_id) \
                .filter(ProjectEntryResource.resource_id == resource_id) \
                .one()
        except sqlalchemy.orm.exc.NoResultFound:
            raise errors.NotFound()

        flask.g.sql_session.delete(entry_resource)
        flask.g.sql_session.commit()

        return '', 204


@app.route('/api/projects/<int:project_id>/entries/<int:entry_id>/members/<int:member_id>', methods=['PUT', 'DELETE'])
def api_project_entry_member(project_id, entry_id, member_id):
    project = get_project_or_404(project_id)
    account_member = get_project_member_or_403(project)

    if not account_member.access_level.can_edit:
        raise errors.MissingPermission('can_edit')

    if flask.request.method == 'PUT':
        entry_member = ProjectEntryMember(entry_id=entry_id,
                                          member_id=member_id)

        flask.g.sql_session.add(entry_member)
        flask.g.sql_session.commit()

        return '', 201
    elif flask.request.method == 'DELETE':
        try:
            entry_member = flask.g.sql_session.query(ProjectEntryMember) \
                .filter(ProjectEntryMember.entry_id == entry_id) \
                .filter(ProjectEntryMember.member_id == member_id) \
                .one()
        except sqlalchemy.orm.exc.NoResultFound:
            raise errors.NotFound()

        flask.g.sql_session.delete(entry_member)
        flask.g.sql_session.commit()

        return '', 204


@app.route('/api/projects/<int:project_id>/entries/<int:parent_id>/dependencies/<int:child_id>', methods=['PUT', 'DELETE'])
def api_project_entry_dependency(project_id, parent_id, child_id):
    project = get_project_or_404(project_id)
    account_member = get_project_member_or_403(project)

    if not account_member.access_level.can_edit:
        raise errors.MissingPermission('can_edit')

    if flask.request.method == 'PUT':
        dependency = ProjectEntryDependency(parent_id=parent_id,
                                            child_id=child_id)

        flask.g.sql_session.add(dependency)

        try:
            flask.g.sql_session.flush()
        except sqlalchemy.exc.IntegrityError:
            flask.g.sql_session.rollback()
            raise errors.InvalidGraph()

        try:
            chart = Chart(project)
            flask.g.sql_session.commit()
            return '', 201
        except ValueError:
            flask.g.sql_session.rollback()
            raise errors.InvalidGraph()
    elif flask.request.method == 'DELETE':
        try:
            dependency = flask.g.sql_session.query(ProjectEntryDependency) \
                .filter(ProjectEntryDependency.parent_id == parent_id) \
                .filter(ProjectEntryDependency.child_id == child_id) \
                .one()
        except sqlalchemy.orm.exc.NoResultFound:
            raise errors.NotFound()

        flask.g.sql_session.delete(dependency)
        flask.g.sql_session.commit()

        return '', 204


@app.route('/api/projects/<int:project_id>/gantt-chart')
def api_project_gantt_chart(project_id):
    project = get_project_or_404(project_id)
    account_member = get_project_member_or_403(project)

    try:
        chart = Chart(project)
    except ValueError:
        raise errors.NotFound()

    as_json = chart.as_json()
    if as_json is None:
        raise errors.NotFound()

    return flask.jsonify(gantt_chart=as_json)


@app.route('/api/projects/<int:project_id>/members', methods=['GET', 'POST'])
def api_project_members(project_id):
    project = get_project_or_404(project_id)
    account_member = get_project_member_or_403(project)

    if flask.request.method == 'GET':
        members = [member.as_json() for member in project.members]
        return flask.jsonify(members=members)
    elif flask.request.method == 'POST':
        if not account_member.access_level.can_administrate:
            raise errors.MissingPermission('can_administrate')

        form = forms.ApiAddProjectMember.from_json(flask.request.json)
        if form.validate():
            members = project.members
            member = ProjectMember(form.email_address.record.account,
                                   AccessLevel[form.access_level.data])
            members.append(member)
            try:
                flask.g.sql_session.commit()
            except sqlalchemy.orm.exc.FlushError:
                raise errors.AlreadyExists()
            return flask.jsonify(member=member.as_json()), 201
        else:
            raise errors.InvalidFormData(form)


@app.route('/api/projects/<int:project_id>/members/<int:member_id>', methods=['PATCH', 'DELETE'])
def api_project_member(project_id, member_id):
    project = get_project_or_404(project_id)
    account_member = get_project_member_or_403(project)

    if not account_member.access_level.can_administrate:
        raise errors.MissingPermission('can_administrate')

    member = flask.g.sql_session.query(ProjectMember) \
        .filter(ProjectMember.id == member_id).one()
    if member.project != project:
        raise errors.NotFound()

    if flask.request.method == 'PATCH':
        form = forms.ApiUpdateProjectMember.from_json(flask.request.json)
        if form.validate():
            if form.access_level.raw_data:
                new_access_level = AccessLevel[form.access_level.data]
                if new_access_level.owner:
                    if not account_member.access_level.owner:
                        raise errors.MissingPermission('owner')

                member.access_level = new_access_level

            flask.g.sql_session.commit()

            return '', 204
        else:
            raise errors.InvalidFormData(form)
    elif flask.request.method == 'DELETE':
        if member.access_level.owner:
            raise errors.MethodNotAllowed()

        flask.g.sql_session.delete(member)
        flask.g.sql_session.commit()

        return '', 204


@app.route('/api/projects/<int:project_id>/resources', methods=['GET', 'POST'])
def api_project_resources(project_id):
    project = get_project_or_404(project_id)
    account_member = get_project_member_or_403(project)

    if flask.request.method == 'GET':
        resources = [res.as_json() for res in project.resources]
        return flask.jsonify(resources=resources)
    elif flask.request.method == 'POST':
        if not account_member.access_level.can_administrate:
            raise errors.MissingPermission('can_administrate')

        form = forms.ApiAddProjectResource.from_json(flask.request.json)
        if form.validate():
            resources = project.resources
            resource = ProjectResource(form.name.data, form.description.data,
                                       form.icon.data, form.amount.data,
                                       form.reusable.data)
            resources.append(resource)
            try:
                flask.g.sql_session.commit()
            except sqlalchemy.orm.exc.FlushError:
                raise errors.AlreadyExists()
            return flask.jsonify(resource=resource.as_json()), 201
        else:
            raise errors.InvalidFormData(form)


@app.route('/api/projects/<int:project_id>/resources/<int:resource_id>', methods=['PATCH', 'DELETE'])
def api_project_resource(project_id, resource_id):
    project = get_project_or_404(project_id)
    account_member = get_project_member_or_403(project)

    if not account_member.access_level.can_administrate:
        raise errors.MissingPermission('can_administrate')

    resource = get_project_resource_or_404(resource_id)

    if flask.request.method == 'PATCH':
        form = forms.ApiUpdateProjectResource.from_json(flask.request.json)
        if form.validate():
            if form.name.raw_data:
                resource.name = form.name.data

            if form.description.raw_data:
                resource.description = form.description.data

            if form.icon.raw_data:
                resource.icon = form.icon.data

            if form.amount.raw_data:
                resource.amount = form.amount.data

            if form.reusable.raw_data:
                resource.reusable = form.reusable.data

            flask.g.sql_session.commit()

            return '', 204
        else:
            raise errors.InvalidFormData(form)
    elif flask.request.method == 'DELETE':
        flask.g.sql_session.delete(resource)
        flask.g.sql_session.commit()
        return '', 204


def error_handler(e):
    # fill up the error object with a name, description, code and details
    error = {
        'name': type(e).__name__,
        'description': e.description,
        'code': e.code
    }

    # not all errors will have details
    try:
        error['details'] = e.details
    except AttributeError:
        pass

    return flask.jsonify(error=error), e.code

for code in range(400, 499):
    app.errorhandler(code)(error_handler)
