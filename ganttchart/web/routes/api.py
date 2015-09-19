"""
Routes for the API.
"""

import datetime

import flask
import sqlalchemy

from ganttchart import database
from ganttchart.chart import Chart
from ganttchart.models import generate_key, AccessLevel, Account, AccountEmailAddress, \
    Project, ProjectCalendarHoliday, ProjectEntry, ProjectEntryDependency, \
    ProjectEntryMember, ProjectEntryType, ProjectEntryResource, \
    ProjectMember, ProjectResource, ProjectStar, Session as SqlSession
from ganttchart.web import errors, forms


blueprint = flask.Blueprint('api', __name__, url_prefix='/api')


@blueprint.before_request
def check_csrf_token(*args, **kwargs):
    header = flask.request.headers.get('X-CSRF-Token', None)
    cookie = flask.request.cookies.get('CSRF-Token', None)

    if header is None or cookie is None:
        raise errors.MissingCsrfToken()

    if header != cookie:
        raise errors.MissingCsrfToken()


@blueprint.route('/account', methods=['PATCH'])
def change_account():
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


@blueprint.route('/projects/<int:project_id>')
def project(project_id):
    project = get_project_or_404(project_id)
    account_member = get_project_member_or_403(project)

    if not account_member.access_level.can_view:
        raise errors.MissingPermission('can_view')

    return flask.jsonify(project=project.as_json())


@blueprint.route('/projects/<int:project_id>/calendar', methods=['GET', 'PATCH'])
def project_calendar(project_id):
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


@blueprint.route('/projects/<int:project_id>/calendar/holidays', methods=['POST'])
def project_calendar_holidays(project_id):
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


@blueprint.route('/projects/<int:project_id>/calendar/holidays/<int:holiday_id>', methods=['DELETE'])
def project_calendar_holiday(project_id, holiday_id):
    project = get_project_or_404(project_id)
    account_member = get_project_member_or_403(project)
    if not account_member.access_level.can_administrate:
        raise errors.MissingPermission('can_administrate')

    target_holiday = flask.g.sql_session.query(ProjectCalendarHoliday) \
        .filter(ProjectCalendarHoliday.id == holiday_id).one()

    flask.g.sql_session.delete(target_holiday)
    flask.g.sql_session.commit()
    return '', 204


@blueprint.route('/projects/<int:project_id>/entries', methods=['GET', 'POST'])
def project_entries(project_id):
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


@blueprint.route('/projects/<int:project_id>/entries/<int:entry_id>', methods=['GET', 'PATCH', 'DELETE'])
def project_entry(project_id, entry_id):
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


@blueprint.route('/projects/<int:project_id>/entries/<int:entry_id>/resources/<int:resource_id>', methods=['PUT', 'DELETE'])
def project_entry_resource(project_id, entry_id, resource_id):
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


@blueprint.route('/projects/<int:project_id>/entries/<int:entry_id>/members/<int:member_id>', methods=['PUT', 'DELETE'])
def project_entry_member(project_id, entry_id, member_id):
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


@blueprint.route('/projects/<int:project_id>/entries/<int:parent_id>/dependencies/<int:child_id>', methods=['PUT', 'DELETE'])
def project_entry_dependency(project_id, parent_id, child_id):
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


@blueprint.route('/projects/<int:project_id>/gantt-chart')
def project_gantt_chart(project_id):
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


@blueprint.route('/projects/<int:project_id>/members', methods=['GET', 'POST'])
def project_members(project_id):
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


@blueprint.route('/projects/<int:project_id>/members/<int:member_id>', methods=['PATCH', 'DELETE'])
def project_member(project_id, member_id):
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


@blueprint.route('/projects/<int:project_id>/resources', methods=['GET', 'POST'])
def project_resources(project_id):
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


@blueprint.route('/projects/<int:project_id>/resources/<int:resource_id>', methods=['PATCH', 'DELETE'])
def project_resource(project_id, resource_id):
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
    blueprint.errorhandler(code)(error_handler)
