from werkzeug.exceptions import BadRequest, Conflict, Forbidden, \
    NotFound as BaseNotFound, MethodNotAllowed, Unauthorized


# 400
class InvalidFormData(BadRequest):
    description = 'Invalid form data.'

    def __init__(self, form=None, errors=None):
        super().__init__()

        if form is None and errors is None:
            raise ValueError('Form and errors cannot be none.')
        if form is not None and errors is not None:
            raise ValueError('Form and errors cannot both be set.')

        if form is not None:
            self.details = form.errors
        if errors is not None:
            self.details = errors


# 401
class NotAuthenticated(Unauthorized):
    description = 'Wrong account ID or password.'


# 403
class MissingPermission(Forbidden):
    description = 'Missing required permission.'

    def __init__(self, name):
        super().__init__()

        self.details = {'name': name}


# 404
class NotFound(BaseNotFound):
    def __init__(self, resource=None):
        super().__init__()

        if resource is not None:
            self.details = {'resource': resource}


# 409
class AlreadyExists(Conflict):
    description = 'Resource already exists.'


class InvalidGraph(Conflict):
    description = 'This would make an invalid graph.'
