"""Models."""

import datetime
from enum import Enum
import hashlib
import os

import flask
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

    def as_json(self):
        return {
            'id': self.id,
            'display_name': self.display_name,
            'photo_url': self.primary_email_address.gravatar(128),
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

    def send_verify_email(self):
        if self.verified:
            return

        url = flask.url_for('.account_verify_email', id=self.id,
                            key=self.verify_key, _external=True)
        email = emails.VerifyEmailAddress(self.email_address, url)
        with emails.Mailer() as mailer:
            mailer.send(email)

    @property
    def as_md5_string(self):
        h = hashlib.md5()
        h.update(self.email_address.lower().encode('utf-8'))
        return h.hexdigest()

    def gravatar(self, size=40):
        return 'https://www.gravatar.com/avatar/{}?s={}' \
               .format(self.as_md5_string, size)


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
        self.start_date = creation_date.date()
        self.members.append(ProjectMember(creator, AccessLevel.owner))

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


class ProjectMember(Base):
    __tablename__ = 'project_member'

    project = relationship('Project', backref='members')
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

    def as_json(self):
        return {
            'account': self.account.as_json(),
            'access_level': self.access_level.as_json(),
        }


class ProjectStar(Base):
    __tablename__ = 'project_star'

    project = relationship('Project', backref='stars')
    account = relationship('Account', backref='stars')


class Task(Base):
    __tablename__ = 'task'

    project = relationship('Project', backref='tasks')

    def __init__(self, name, description, time_estimates, project):
        super().__init__(name=name, description=description)

        self.optimistic_time_estimate = time_estimates[0]
        self.normal_time_estimate = time_estimates[1]
        self.pessimistic_time_estimate = time_estimates[2]
        self.project = project
        self.creation_date = datetime.datetime.now()

    @property
    def expected_time(self):
        seconds = (self.optimistic_time_estimate + \
            4 * self.normal_time_estimate + \
            self.pessimistic_time_estimate) / 6
        return datetime.timedelta(seconds=seconds)

    def as_json(self):
        return {
            'id': self.id,
            'time_estimates': {
                'optimistic': self.optimistic_time_estimate,
                'normal': self.normal_time_estimate,
                'pessimistic': self.pessimistic_time_estimate
            },
            'expected_time': self.expected_time.total_seconds(),
            'dependencies': [{'id': d.dependency.id} for d in self.dependencies]
        }


class TaskDependency(Base):
    __tablename__ = 'task_dependency'

    task = relationship('Task', backref='dependencies',
                        foreign_keys='TaskDependency.task_id')
    dependency = relationship('Task',
                              foreign_keys='TaskDependency.dependency_id')
