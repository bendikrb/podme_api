""" """

PODME_AUTH_USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64; rv:94.0) Gecko/20100101 Firefox/94.0'

PODME_API_URL = "https://api.podme.com/web/api/v2{endpoint}"
PODME_AUTH_CLIENT_ID = "6e1a23e7-71ec-4483-918a-25c33852c9c9"
PODME_AUTH_TENANT = "reacthello"
PODME_AUTH_LOGIN_USER_FLOW = "B2C_1_web_combined_login"
PODME_AUTH_URL = "https://{tenant}.b2clogin.com".format(tenant=PODME_AUTH_TENANT)
PODME_AUTH_TOKEN_URL = "https://{tenant}.b2clogin.com/{tenant}.onmicrosoft.com/{login_user_flow}".format(
    tenant=PODME_AUTH_TENANT,
    login_user_flow=PODME_AUTH_LOGIN_USER_FLOW,
)
PODME_AUTH_REDIRECT_URI = "https://podme.com/static/redirect.html"

PODME_SCHIBSTED_AUTH_DOMAIN = "https://payment.schibsted.no"
PODME_SCHIBSTED_AUTH_URL_BASE = f"{PODME_SCHIBSTED_AUTH_DOMAIN}/oauth/authorize"
PODME_SCHIBSTED_AUTH_CLIENT_ID = "626bcf5e1332f10a4997c29a"
PODME_SCHIBSTED_AUTH_REDIRECT = "https://podme.com/auth/handleSchibstedLogin"
PODME_SCHIBSTED_AUTH_RETURN_URL = "https://podme.com/no/oppdag"
PODME_SCHIBSTED_AUTH_SCOPE = "openid+email"
PODME_SCHIBSTED_AUTH_RESPONSE_TYPE = "code"
PODME_SCHIBSTED_AUTH_CSRF_URL = f"{PODME_SCHIBSTED_AUTH_DOMAIN}/authn/api/settings/csrf?" \
                                f"client_id={PODME_SCHIBSTED_AUTH_CLIENT_ID}"
PODME_SCHIBSTED_AUTH_LOGIN_URL = f"{PODME_SCHIBSTED_AUTH_DOMAIN}/authn/api/identity/login/?" \
                                 f"client_id={PODME_SCHIBSTED_AUTH_CLIENT_ID}"
PODME_SCHIBSTED_AUTH_FINISH_URL = f"{PODME_SCHIBSTED_AUTH_DOMAIN}/authn/identity/finish/?" \
                                  f"client_id={PODME_SCHIBSTED_AUTH_CLIENT_ID}"
