""" """


class AuthorizationSignInError(Exception):
    """ """
    def __init__(self, err_no, err_msg):
        self.err_no = err_no
        self.err_msg = err_msg


class AuthorizationError(Exception):
    """ """
    pass


class AccessDeniedError(Exception):
    """ """
    pass
