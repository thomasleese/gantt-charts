import logging
import os
import smtplib


logger = logging.getLogger(__name__)


class Mailer:
    """
    A Mailer represents a connection to an SMTP server.

    It can be used with a context manager, like this::

        mailer = Mailer(...)
        with mailer:
            mailer.send(msg)

    However, using the ``open`` and ``close`` methods is also available.
    """

    def __init__(self, host=None, port=None, use_starttls=None,
                 use_ssl=None, use_lmtp=None, user=None, password=None,
                 testing=None):
        self.testing = self._env_arg(testing, 'TESTING', bool)
        self.host = self._env_arg(host, 'HOST')
        self.port = self._env_arg(port, 'PORT')
        self.use_starttls = self._env_arg(use_starttls, 'USE_STARTTLS', bool)
        self.use_ssl = self._env_arg(use_ssl, 'USE_SSL', bool)
        self.use_lmtp = self._env_arg(use_lmtp, 'USE_LMTP', bool)
        self.user = self._env_arg(user, 'USER')
        self.password = self._env_arg(password, 'PASSWORD')
        self._smtp = None

    def _env_arg(self, passed_value, key, conversion=str,
                 prefix='GANTT_CHARTS_MAIL_'):
        if passed_value is not None:
            return passed_value

        key = prefix + key

        if conversion in (str, int):
            try:
                return conversion(os.environ[key])
            except KeyError:
                if self.testing:
                    return None
                else:
                    raise KeyError('Missing environment variable: {}.'.format(key))
        elif conversion == bool:
            return key in os.environ
        else:
            raise ValueError('Unknown conversion type.')

    @staticmethod
    def _create_smtp(host, port, use_starttls, use_ssl, use_lmtp):
        """Create an approriate SMTP object based on the arguments passed."""

        logger.debug("Creating SMTP connection to %s:%d.", host, port)

        if (use_starttls and use_ssl) or (use_ssl and use_lmtp) \
            or (use_starttls and use_lmtp):
            raise ValueError("You can only pick a single server type.")

        if use_starttls:
            smtp = smtplib.SMTP(host, port)
            smtp.starttls()
            smtp.ehlo()
            return smtp
        elif use_ssl:
            return smtplib.SMTP_SSL(host, port)
        elif use_lmtp:
            return smtplib.LMTP(host, port)
        else:
            return smtplib.SMTP(host, port)

    def open(self):
        """Open the connection to the SMTP server."""

        if self.testing:
            return

        if self._smtp is not None:
            raise RuntimeError("Already connected to an SMTP server.")

        logger.debug("Opening connection to %s:%d.", self.host, self.port)

        self._smtp = self._create_smtp(self.host, self.port, self.use_starttls,
                                       self.use_ssl, self.use_lmtp)
        if self.user is not None or self.password is not None:
            logger.debug("Logging in to %s:%d server.", self.host, self.port)
            self._smtp.login(self.user, self.password)

    def close(self):
        """Close the connection to the SMTP server."""

        if self.testing:
            return

        if self._smtp is None:
            raise RuntimeError("Not connected to an SMTP server.")

        logger.debug("Closing connection to %s:%d.", self.host, self.port)

        self._smtp.quit()
        self._smtp = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def send(self, message):
        """
        Send an email message.

        This method returns the message that it gets sent for convenience.
        """

        logger.info("Sending '%s' to '%s'.", message["Subject"],
                                              message["To"])

        if self.testing:
            return

        logger.debug(message.as_string())

        self._smtp.send_message(message)

        return message

    def send_many(self, messages):
        """
        Send many messages with one function call.

        This returns a list of messages as returned by the ``send`` method.
        """

        results = []
        for message in messages:
            results.append(self.send(message))
        return results
