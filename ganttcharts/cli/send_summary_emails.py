import datetime
import time

from .. import emails
from ..database import get_sql_connection
from ..models import Account, Session as SqlSession


__description__ = 'Send out summary emails.'


def send_out_emails():
    session = SqlSession()

    today = datetime.date.today()

    accounts = session.query(Account) \
        .filter(Account.receive_summary_email == True)  # noqa
    for account in accounts:
        try:
            email = emails.Summary(account, today)
        except RuntimeError:  # no tasks
            continue

        with emails.Mailer() as mailer:
            mailer.send(email)


def command(args):
    get_sql_connection()

    if args.forever:
        while True:
            tomorrow = datetime.datetime.utcnow() + datetime.timedelta(days=1)
            tomorrow = tomorrow.replace(hour=4, minute=0)

            diff = tomorrow - datetime.datetime.utcnow()
            time.sleep(diff.total_seconds())

            send_out_emails()
    else:
        send_out_emails()


def add_subparser(subparsers):
    parser = subparsers.add_parser('send-summary-emails', help=__description__)
    parser.add_argument('--forever', action='store_true')
    parser.set_defaults(func=command)
