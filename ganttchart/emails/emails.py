import email.mime.multipart
import email.mime.text

import jinja2


class Email(email.mime.multipart.MIMEMultipart):
    def __init__(self, name, context):
        super().__init__('alternative')

        self.name = name

        _loader = jinja2.PackageLoader('ganttchart', 'emails/templates')
        self.env = jinja2.Environment(loader=_loader)
        self.context = context

        self['Date'] = email.utils.formatdate()
        self['Subject'] = self.subject
        self['From'] = email.utils.formataddr(('Gantt Chart', 'customers@ganttchart.xyz'))

        self._attach_template('body.txt', 'plain')
        self._attach_template('body.html', 'html')

    def _attach_template(self, name, subtype):
        template = self.env.get_template('{}/{}'.format(self.name, name))

        text = template.render(**self.context)
        mime = email.mime.text.MIMEText(text, subtype)
        self.attach(mime)

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
