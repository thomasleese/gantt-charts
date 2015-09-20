import logging
import os

import flask
from raven.contrib.flask import Sentry
from werkzeug.contrib.fixers import ProxyFix

from .. import database
from ..models import generate_key, Account, AccountEmailAddress, \
    Session as SqlSession
from . import routes


app = flask.Flask('ganttcharts.web')
app.secret_key = os.environ['GANTT_CHARTS_SECRET_KEY']
app.wsgi_app = ProxyFix(app.wsgi_app)


try:
    sentry_dsn = os.environ['SENTRY_DSN']
except KeyError:
    pass
else:
    app.sentry = Sentry(app, dsn=sentry_dsn, logging=True,
                        level=logging.WARNING)


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


@app.errorhandler(500)
def server_error(e):
    return flask.render_template('errors/500.html')


routes.register(app)
