import os

import flask

from .. import database, models
from . import forms


app = flask.Flask('ganttchart.web')
app.secret_key = os.environ['GANTT_CHART_SECRET_KEY']


@app.before_first_request
def configure_database():
    app.sql_engine = database.get_sql_engine()
    app.sql_connection = database.get_sql_connection()


@app.before_request
def configure_session(*args, **kwargs):
    flask.g.sql_session = models.Session()

    if 'account_id' in flask.session:
        account = flask.g.sql_session.query(models.Account) \
            .get(flask.session['account_id'])
        flask.g.account = account


@app.teardown_request
def remove_session(*args, **kwargs):
    models.Session.remove()


@app.route('/')
def home():
    return flask.render_template('home.html')


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
        account = models.Account(form.email_address.data, form.password.data)
        flask.g.sql_session.add(account)
        flask.g.sql_session.commit()

    return flask.render_template('account/signup.html', form=form)


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    del flask.session['account_id']
    return flask.redirect(flask.url_for('.home'))
