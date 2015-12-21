import os

import flask
from raven.contrib.flask import Sentry
from werkzeug.contrib.fixers import ProxyFix

from .. import database
from ..models import generate_key, Account, Session as SqlSession
from . import routes


app = flask.Flask('ganttcharts.web')
app.secret_key = os.environ['SECRET_KEY']
app.wsgi_app = ProxyFix(app.wsgi_app)

sentry = Sentry(app)


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
def set_csrf_token(response):
    if 'account' in flask.g:
        if 'CSRF-Token' not in flask.request.cookies:
            token = generate_key()
            response.set_cookie('CSRF-Token', token, httponly=False)
    return response


@app.teardown_request
def remove_session(*args, **kwargs):
    SqlSession.remove()


@app.errorhandler(404)
def not_found(e):
    return flask.render_template('errors/404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return flask.render_template('errors/500.html'), 500


class Counter:
    def __init__(self):
        self.value = 0

    def increment(self, by=1):
        self.value += by

    def count(self, by=1):
        old_value = self.value
        self.value += by
        return old_value


@app.context_processor
def inject_counter():
    return dict(Counter=Counter)


routes.register(app)
