""" """

PODME_API_URL = "https://api.podme.com/web/api/v2{endpoint}"
PODME_AUTH_USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64; rv:94.0) Gecko/20100101 Firefox/94.0'
PODME_AUTH_CLIENT_ID = "6e1a23e7-71ec-4483-918a-25c33852c9c9"
PODME_AUTH_TENANT = "reacthello"
PODME_AUTH_LOGIN_USER_FLOW = "B2C_1_web_combined_login"
PODME_AUTH_URL = "https://{tenant}.b2clogin.com".format(tenant=PODME_AUTH_TENANT)
PODME_AUTH_TOKEN_URL = "https://{tenant}.b2clogin.com/{tenant}.onmicrosoft.com/{login_user_flow}".format(
    tenant=PODME_AUTH_TENANT,
    login_user_flow=PODME_AUTH_LOGIN_USER_FLOW,
)
PODME_AUTH_REDIRECT_URI = "https://podme.com/static/redirect.html"
