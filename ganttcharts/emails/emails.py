from collections import defaultdict
from email.mime.multipart import MIMEMultipart
import email.mime.text
from email.mime.image import MIMEImage
from pathlib import Path

import jinja2

from .. import chart


class Email(MIMEMultipart):
    def __init__(self, name, context):
        super().__init__('related')

        self.name = name

        path = Path(__file__).parent.parent / 'web' / 'static' / 'images' \
            / 'background.png'
        with path.open('rb') as f:
            image = MIMEImage(f.read())
            image.add_header('Content-ID', '<background-image>')
            self.attach(image)

        _loader = jinja2.PackageLoader('ganttcharts', 'emails/templates')
        self.env = jinja2.Environment(loader=_loader)
        self.context = context

        self['Date'] = email.utils.formatdate()
        self['Subject'] = self.subject

        from_addr = ('Gantt Charts', 'customers@ganttcharts.xyz')
        self['From'] = email.utils.formataddr(from_addr)

        self.mime_alternative = MIMEMultipart('alternative')
        self.attach(self.mime_alternative)

        self._attach_template('body.txt', 'plain')
        self._attach_template('body.html', 'html')

    def _attach_template(self, name, subtype):
        template = self.env.get_template('{}/{}'.format(self.name, name))

        text = template.render(**self.context)
        mime = email.mime.text.MIMEText(text, subtype)
        self.mime_alternative.attach(mime)

    @property
    def subject(self):
        name = '{}/subject.txt'.format(self.name)
        template = self.env.get_template(name)
        return template.render(**self.context).strip()


class VerifyEmailAddress(Email):
    def __init__(self, email_address, url):
        context = {'email_address': email_address, 'url': url}
        super().__init__('verify_email_address', context)

        self['To'] = email_address


class ResetPassword(Email):
    def __init__(self, account, url):
        context = {'account': account, 'url': url}
        super().__init__('reset_password', context)

        self['To'] = account.primary_email_address.email_address


class Summary(Email):
    def __init__(self, account, today):
        blocks_today = defaultdict(list)

        for project in account.projects:
            try:
                gantt_chart = chart.Chart(project)
            except chart.CyclicGraphError:
                continue

            for block in gantt_chart.blocks.values():
                if block.entry.type.name == 'task' \
                        and block.applies_to(today, account):
                    blocks_today[project].append(block)

        if not blocks_today:
            raise RuntimeError('No tasks for today.')

        context = {'account': account, 'blocks_today': blocks_today}
        super().__init__('summary', context)

        self['To'] = account.primary_email_address.email_address
