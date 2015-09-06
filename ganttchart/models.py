"""Models."""

import datetime
import hashlib
import os

import sqlalchemy
from sqlalchemy import event, Column, DateTime, Integer, LargeBinary, \
    MetaData, String, Table, ForeignKey, UniqueConstraint
from sqlalchemy.orm import backref, deferred, scoped_session, sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base, DeferredReflection
from sqlalchemy.ext.hybrid import hybrid_property
from passlib.context import CryptContext


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

        self.email_addresses.append(AccountEmailAddress(email_address))
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
    def projects(self):
        for member in self.project_members:
            yield member.project


class AccountEmailAddress(Base):
    __tablename__ = 'account_email_address'

    account = relationship('Account',
                           backref=backref('email_addresses',
                                           cascade='all, delete-orphan'),
                           cascade='all')

    def __init__(self, email_address, verified=False, verify_key=None):
        if verify_key is None:
            verify_key = generate_key()

        super().__init__(email_address=email_address, verified=verified,
                         verify_key=verify_key)

    def __str__(self):
        return self.email_address

    @property
    def as_md5_string(self):
        h = hashlib.md5()
        h.update(self.email_address.lower().encode('utf-8'))
        return h.hexdigest()

    def gravatar(self, size=40):
        return 'https://www.gravatar.com/avatar/{}?s={}' \
               .format(self.as_md5_string, size)


class Project(Base):
    __tablename__ = 'project'

    def __init__(self, name, creator, creation_date=None):
        super().__init__()

        if creation_date is None:
            creation_date = datetime.datetime.now()

        self.name = name
        self.creation_date = creation_date
        self.start_date = creation_date.date()
        self.members.append(ProjectMember(account=creator))

    def starred_by(self, account):
        for star in self.stars:
            if star.account == account:
                return True
        return False


class ProjectMember(Base):
    __tablename__ = 'project_member'

    project = relationship('Project', backref='members')
    account = relationship('Account', backref='project_members')


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


class TaskDependency(Base):
    __tablename__ = 'task_dependency'

    task = relationship('Task', backref='dependencies',
                        foreign_keys='TaskDependency.task_id')
    dependency = relationship('Task',
                              foreign_keys='TaskDependency.dependency_id')
