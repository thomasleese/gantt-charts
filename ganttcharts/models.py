"""Models."""

import datetime
from enum import Enum
import hashlib
import math
import os

import flask
from pandas.tseries.offsets import BusinessHour, CustomBusinessDay
import sqlalchemy
from sqlalchemy import event, Column, DateTime, Integer, LargeBinary, \
    MetaData, String, Table, ForeignKey, UniqueConstraint
from sqlalchemy.orm import backref, deferred, scoped_session, sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base, DeferredReflection
from sqlalchemy.ext.hybrid import hybrid_property
from passlib.context import CryptContext

from . import emails


Base = declarative_base(cls=DeferredReflection)
Session = scoped_session(sessionmaker())


password_context = CryptContext(
    schemes=['pbkdf2_sha256'],
    default='pbkdf2_sha256',
    all__vary_rounds=0.1,
    pbkdf2_sha256__default_rounds=8000
)


def generate_key(length=512):
    h = hashlib.sha256()
    h.update(os.urandom(length))
    return h.hexdigest()


class Account(Base):
    __tablename__ = 'account'

    def __init__(self, display_name, email_address, password):
        super().__init__(display_name=display_name)

        self.email_addresses.append(AccountEmailAddress(email_address,
                                                        primary=True))
        self.password = password
        self.creation_date = datetime.datetime.now()

    @property
    def password(self):
        raise NotImplementedError()

    @password.setter
    def password(self, value):
        self.password_hashed = password_context.encrypt(value)

    def is_password_correct(self, other):
        return password_context.verify(other, self.password_hashed)

    @property
    def primary_email_address(self):
        for email_address in self.email_addresses:
            if email_address.primary:
                return email_address
        return self.email_addresses[0]

    @property
    def initials(self):
        names = self.display_name.split()
        if len(names) == 1:
            return names[0][0]
        else:
            return names[0][0] + names[-1][0]

    @property
    def projects(self):
        for member in self.project_members:
            yield member.project

    @property
    def my_projects(self):
        for member in self.project_members:
            if member.access_level.owner or member.access_level.can_administrate:
                yield member.project

    @property
    def shared_projects(self):
        for member in self.project_members:
            if (member.access_level.can_view or member.access_level.can_edit) \
                    and not (member.access_level.owner \
                        or member.access_level.can_administrate):
                yield member.project

    @property
    def should_send_password_reset_email(self):
        if self.reset_password_key is None \
                or self.reset_password_key_expiration_date is None:
            return False

        if self.last_reset_password_email_date is None:
            return True

        one_day_ago = datetime.datetime.now() - datetime.timedelta(hours=1)
        if self.last_reset_password_email_date < one_day_ago:
            return True

        return False

    def send_reset_password_email(self):
        if not self.should_send_password_reset_email:
            return

        url = flask.url_for('.account_reset', account_id=self.id,
                            reset_password_key=self.reset_password_key,
                            _external=True)
        email = emails.ResetPassword(self, url)
        with emails.Mailer() as mailer:
            mailer.send(email)

        self.last_reset_password_email_date = datetime.datetime.now()

    def reset_password(self):
        self.reset_password_key = generate_key()
        self.reset_password_key_creation_date = datetime.datetime.now()
        self.reset_password_key_expiration_date = datetime.datetime.now() \
            + datetime.timedelta(hours=2)

        self.send_reset_password_email()

    def as_json(self):
        return {
            'id': self.id,
            'display_name': self.display_name,
            'photo_url': '/account/{}/avatar'.format(self.id)
        }


class AccountEmailAddress(Base):
    __tablename__ = 'account_email_address'

    account = relationship('Account', backref=backref('email_addresses'))

    def __init__(self, email_address, primary=False, verified=False,
                 verify_key=None):
        if verify_key is None:
            verify_key = generate_key()

        super().__init__(email_address=email_address, primary=primary,
                         verified=verified, verify_key=verify_key)

    def __str__(self):
        return self.email_address

    @property
    def should_send_verification_email(self):
        if self.verified:
            return False

        if self.last_verification_email_date is None:
            return True

        one_day_ago = datetime.datetime.now() - datetime.timedelta(days=1)
        if self.last_verification_email_date < one_day_ago:
            return True

        return False

    def send_verify_email(self):
        if not self.should_send_verification_email:
            return

        url = flask.url_for('.account_verify_email', id=self.id,
                            key=self.verify_key, _external=True)
        email = emails.VerifyEmailAddress(self.email_address, url)
        with emails.Mailer() as mailer:
            mailer.send(email)

        self.last_verification_email_date = datetime.datetime.now()


@event.listens_for(AccountEmailAddress, 'after_insert')
def account_created(mapper, connection, email_address):
    email_address.send_verify_email()


class AccessLevel(Enum):
    owner = (True, True, True, True)
    administrator = (False, True, True, True)
    editor = (False, False, True, True)
    viewer = (False, False, False, True)
    banned = (False, False, False, False)

    def __init__(self, owner, can_administrate, can_edit, can_view):
        self.owner = owner
        self.can_administrate = can_administrate
        self.can_edit = can_edit
        self.can_view = can_view

    @property
    def description(self):
        if self.owner:
            return 'Owner'
        elif self.can_administrate:
            return 'Administrator'
        elif self.can_edit:
            return 'Can edit'
        elif self.can_view:
            return 'Can view'
        else:
            return 'Banned'

    @property
    def is_banned(self):
        return not (self.owner or self.can_administrate or self.can_edit \
            or self.can_view)

    def as_json(self):
        return {
            'id': self.name,
            'description': self.description,
            'owner': self.owner,
            'can_administrate': self.can_administrate,
            'can_edit': self.can_edit,
            'can_view': self.can_view
        }


class Project(Base):
    __tablename__ = 'project'

    def __init__(self, name, description, creator, creation_date=None):
        super().__init__(name=name, description=description)

        if creation_date is None:
            creation_date = datetime.datetime.now()

        self.creation_date = creation_date
        self.members.append(ProjectMember(creator, AccessLevel.owner))
        self.calendar = ProjectCalendar()

    def starred_by(self, account):
        for star in self.stars:
            if star.account == account:
                return True
        return False

    def get_member(self, account):
        try:
            account_id = account.id
        except AttributeError:
            account_id = account

        for member in self.members:
            if member.account.id == account_id:
                return member
        return None

    def as_json(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
        }


class ProjectCalendar(Base):
    __tablename__ = 'project_calendar'

    project = relationship('Project',
                           backref=backref('calendar', uselist=False))

    def __init__(self):
        super().__init__(works_on_monday=True,
                         works_on_tuesday=True,
                         works_on_wednesday=True,
                         works_on_thursday=True,
                         works_on_friday=True,
                         works_on_saturday=False,
                         works_on_sunday=False,
                         work_starts_at=datetime.time(9),
                         work_ends_at=datetime.time(17),
                         start_date=datetime.datetime.now())

    @property
    def business_hour(self):
        return BusinessHour(start=self.work_starts_at, end=self.work_ends_at)

    @property
    def _weekmask(self):
        return [self.works_on_monday, self.works_on_tuesday,
                self.works_on_wednesday, self.works_on_thursday,
                self.works_on_friday, self.works_on_saturday,
                self.works_on_sunday]

    @property
    def business_day(self):
        holidays = []
        for holiday in self.holidays:
            start_date = holiday.start
            if holiday.days == 1:
                holidays.append(start_date)
            else:
                for i in range(holiday.days + 1):
                    holidays.append(start_date + datetime.timedelta(days=i))

        return CustomBusinessDay(holidays=holidays, weekmask=self._weekmask)

    @property
    def business_day_length(self):
        today = datetime.date.today()
        start = datetime.datetime.combine(today, self.work_starts_at)
        end = datetime.datetime.combine(today, self.work_ends_at)
        return int((end - start).total_seconds() / (60 * 60))

    @property
    def number_working_days(self):
        return sum([1 if x is True else 0 for x in self._weekmask])

    def is_working_date(self, date):
        weekday = date.weekday()
        if self._weekmask[weekday]:
            return True

        for holiday in self.holidays:
            if holiday.start <= date.date() <= holiday.end:
                return True

        return False

    def as_json(self):
        return {
            'start_date': self.start_date.isoformat(),
            'working_week': {
                'monday': self.works_on_monday,
                'tuesday': self.works_on_tuesday,
                'wednesday': self.works_on_wednesday,
                'thursday': self.works_on_thursday,
                'friday': self.works_on_friday,
                'saturday': self.works_on_saturday,
                'sunday': self.works_on_sunday,
                'length': self.number_working_days,
            },
            'working_day': {
                'start': self.work_starts_at.isoformat(),
                'end': self.work_ends_at.isoformat(),
                'length': self.business_day_length,
            },
            'holidays': [h.as_json() for h in self.holidays]
        }


class ProjectCalendarHoliday(Base):
    __tablename__ = 'project_calendar_holiday'

    calendar = relationship('ProjectCalendar', backref='holidays')

    def __init__(self, name, start, end):
        super().__init__(name=name, start=start, end=end)

    @property
    def days(self):
        return (self.end - self.start).days

    def as_json(self):
        return {
            'id': self.id,
            'name': self.name,
            'start': self.start.isoformat(),
            'end': self.end.isoformat(),
        }


class ProjectMember(Base):
    __tablename__ = 'project_member'

    project = relationship('Project', backref=backref('members', order_by='ProjectMember.account_id'))
    account = relationship('Account', backref='project_members')

    def __init__(self, account, access_level):
        super().__init__(account=account, access_level=access_level)

    _access_level = Column('access_level', String)

    @hybrid_property
    def access_level(self):
        return AccessLevel[self._access_level]

    @access_level.setter
    def access_level(self, access_level):
        self._access_level = access_level.name

    @access_level.expression
    def access_level(self):
        return self._access_level

    def as_json(self, minimal=False):
        json = {
            'id': self.id,
            'account': self.account.as_json(),
        }

        if not minimal:
            json['access_level'] = self.access_level.as_json()

        return json


class ProjectResource(Base):
    __tablename__ = 'project_resource'

    project = relationship('Project', backref=backref('resources', order_by='ProjectResource.name'))

    def __init__(self, name, description, icon, amount, reusable):
        super().__init__(name=name, description=description, icon=icon,
                         amount=amount, reusable=reusable)

    def as_json(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'icon': self.icon,
            'amount': self.amount,
            'reusable': self.reusable,
        }


class ProjectStar(Base):
    __tablename__ = 'project_star'

    project = relationship('Project', backref='stars')
    account = relationship('Account', backref='stars')


class ProjectEntryType(Enum):
    task = 'task'
    milestone = 'milestone'


class ProjectEntry(Base):
    __tablename__ = 'project_entry'

    project = relationship('Project', backref=backref('entries', order_by='ProjectEntry.creation_date'))

    def __init__(self, name, description, type, normal_time_estimate,
                 pessimistic_time_estimate, project):
        super().__init__(name=name, description=description)

        self.type = type
        self.normal_time_estimate = normal_time_estimate
        self.pessimistic_time_estimate = pessimistic_time_estimate
        self.project = project
        self.creation_date = datetime.datetime.now()

    _type = Column('type', String)

    @hybrid_property
    def type(self):
        return ProjectEntryType[self._type]

    @type.setter
    def type(self, type):
        self._type = type.name

    @type.expression
    def type(self):
        return self._type

    def as_json(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'type': self._type,
            'time_estimates': {
                'normal': self.normal_time_estimate,
                'pessimistic': self.pessimistic_time_estimate
            },
            'dependencies': [dep.as_json() for dep in self.dependencies],
            'resources': [res.as_json() for res in self.resources],
            'members': [member.as_json() for member in self.members],
        }


class ProjectEntryDependency(Base):
    __tablename__ = 'project_entry_dependency'

    parent = relationship('ProjectEntry', backref='dependencies',
                          foreign_keys='ProjectEntryDependency.parent_id')
    child = relationship('ProjectEntry', backref='dependees',
                         foreign_keys='ProjectEntryDependency.child_id')

    def as_json(self):
        return {
            'parent': {'id': self.parent_id},
            'child': {'id': self.child_id},
        }


class ProjectEntryMember(Base):
    __tablename__ = 'project_entry_member'

    entry = relationship('ProjectEntry', backref='members')
    member = relationship('ProjectMember', backref='entries')

    def as_json(self):
        return {
            'member': self.member.as_json(minimal=True),
            'entry': {'id': self.entry_id},
        }


class ProjectEntryResource(Base):
    __tablename__ = 'project_entry_resource'

    entry = relationship('ProjectEntry', backref='resources')
    resource = relationship('ProjectResource', backref='entries')

    def as_json(self):
        return {
            'amount': self.amount,
            'resource': self.resource.as_json(),
            'entry': {'id': self.entry_id},
        }
