import flask
from wtforms import Form
from wtforms.fields import BooleanField, DateField, IntegerField, FormField, \
    PasswordField, StringField
from wtforms.validators import DataRequired, Email, Length, Optional, \
    ValidationError
import wtforms_json

from ..models import AccountEmailAddress


wtforms_json.init()


class Unique:
    def __init__(self, model, column, message=None):
        self.model = model
        self.column = column

        if message is None:
            message = 'Already taken.'
        self.message = message

    def __call__(self, form, field):
        column = getattr(self.model, self.column)

        result = flask.g.sql_session.query(self.model) \
            .filter(column == field.data).first()
        if result is not None:
            raise ValidationError(self.message)


class Exists:
    def __init__(self, model, column, message=None):
        self.model = model
        self.column = column

        if message is None:
            message = 'Does not exist.'
        self.message = message

    def __call__(self, form, field):
        column = getattr(self.model, self.column)

        result = flask.g.sql_session.query(self.model) \
            .filter(column == field.data).first()

        if result is None:
            raise ValidationError(self.message)
        else:
            field.record = result


class PasswordCorrect(object):
    def __init__(self, other_field_names=None, message=None):
        if isinstance(other_field_names, str):
            self.other_field_names = other_field_names.split(',')
        elif isinstance(other_field_names, list):
            self.other_field_names = other_field_names
        else:
            self.other_field_names = []

        if message is None:
            message = 'Incorrect password.'
        self.message = message

    @staticmethod
    def get_record(form, field_names):
        for field_name in field_names:
            field = form._fields.get(field_name)
            try:
                return field.record
            except AttributeError:
                pass

        try:
            return flask.g.account
        except AttributeError:
            return None

    def __call__(self, form, field):
        record = self.get_record(form, self.other_field_names)
        if record is not None:
            try:
                is_password_correct = record.is_password_correct
            except AttributeError:
                is_password_correct = record.account.is_password_correct

            if is_password_correct(field.data):
                field.record = record
                return

        raise ValidationError(self.message)


class SignUp(Form):
    display_name = StringField('Display Name', validators=[DataRequired()])
    email_address = StringField('Email Address',
                                validators=[DataRequired(), Email(),
                                            Unique(AccountEmailAddress, 'email_address')])
    password = PasswordField('Password', validators=[DataRequired(), Length(8)])


class LogIn(Form):
    email_address = StringField('Email Address',
                                validators=[DataRequired(), Exists(AccountEmailAddress, 'email_address')])
    password = StringField('Password', validators=[DataRequired(), PasswordCorrect('email_address')])


class AccountReset1(Form):
    email_address = StringField('Email Address',
                                validators=[DataRequired(), Email(),
                                            Exists(AccountEmailAddress,
                                                   'email_address')])


class AccountReset2(Form):
    new_password = StringField('New Password',
                               validators=[DataRequired(), Length(8)])


class CreateProject(Form):
    name = StringField('Name', validators=[DataRequired()])
    description = StringField('Description', validators=[Optional()],
                              description='Enter a few words about your project — or leave it out entirely.')


class ApiAddProjectEntry(Form):
    name = StringField('Name', validators=[DataRequired()])
    description = StringField('Description', validators=[Optional()])
    type = StringField('Type', validators=[DataRequired()])
    normal_time_estimate = IntegerField('Normal Time Estimate', validators=[DataRequired()])
    pessimistic_time_estimate = IntegerField('Pessimistic Time Estimate', validators=[DataRequired()])


class ApiChangeProjectEntry(Form):
    name = StringField()
    description = StringField()
    type = StringField()
    normal_time_estimate = IntegerField()
    pessimistic_time_estimate = IntegerField()


class ApiAddProjectMember(Form):
    email_address = StringField('Email Address',
                                validators=[DataRequired(), Email(),
                                            Exists(AccountEmailAddress,
                                                   'email_address')])
    access_level = StringField('Access Level', validators=[DataRequired()])


class ApiUpdateProjectMember(Form):
    access_level = StringField('Access Level')


class ApiAddProjectResource(Form):
    name = StringField('Name', validators=[DataRequired()])
    description = StringField('Description', validators=[Optional()])
    icon = StringField('Icon', validators=[DataRequired()])
    amount = IntegerField('Amount', validators=[DataRequired()])
    reusable = BooleanField('Reusable')


class ApiUpdateProjectResource(Form):
    name = StringField('Name')
    description = StringField('Description')
    icon = StringField('Icon')
    amount = IntegerField('Amount')
    reusable = BooleanField('Reusable')


class WorkingWeek(Form):
    monday = BooleanField()
    tuesday = BooleanField()
    wednesday = BooleanField()
    thursday = BooleanField()
    friday = BooleanField()
    saturday = BooleanField()
    sunday = BooleanField()


class WorkingDay(Form):
    start = StringField()
    end = StringField()


class ApiChangeProjectCalendar(Form):
    working_week = FormField(WorkingWeek)
    working_day = FormField(WorkingDay)
    start_date = DateField()


class ApiAddCalendarHoliday(Form):
    name = StringField('Name', validators=[DataRequired()])
    start = DateField('Start', validators=[DataRequired()])
    end = DateField('End', validators=[DataRequired()])


class ApiAddProjectEntryResource(Form):
    amount = IntegerField(validators=[DataRequired()])


class EmailAddress(Form):
    email_address = StringField('Email Address',
                                validators=[DataRequired(), Email(),
                                            Unique(AccountEmailAddress,
                                                   'email_address')])


class ApiChangeAccount(Form):
    display_name = StringField('Display Name', validators=[DataRequired()])


class ChangePassword(Form):
    old_password = PasswordField('Old Password',
                                 validators=[DataRequired(), PasswordCorrect()])
    new_password = PasswordField('New Password',
                                 validators=[DataRequired(), Length(8)])
