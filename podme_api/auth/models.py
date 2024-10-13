from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from mashumaro import field_options

from podme_api.models import BaseDataClassORJSONMixin


@dataclass
class PodMeUserCredentials:
    """Represents user credentials for PodMe authentication.

    Attributes:
        email (str): The user's email address.
        password (str): The user's password.

    """

    email: str
    password: str


@dataclass
class SchibstedCredentials(BaseDataClassORJSONMixin):
    """Represents Schibsted authentication credentials.

    Attributes:
        scope (str): The scope of the authentication.
        user_id (str): The user's unique identifier.
        is_admin (bool): Indicates if the user has admin privileges.
        token_type (str): The type of authentication token.
        access_token (str): The access token for authentication.
        refresh_token (str): The refresh token for obtaining new access tokens.
        expires_in (int): The token expiration time in seconds.
        id_token (str): The ID token for the authenticated user.
        server_time (datetime): The server time when the token was issued.
        expiration_time (datetime): The expiration time of the token.
        account_created (bool | None): Indicates if the account was newly created.
        email (str | None): The user's email address.

    """

    scope: str
    user_id: str
    is_admin: bool
    token_type: str
    access_token: str
    refresh_token: str
    expires_in: int
    id_token: str
    server_time: datetime = field(
        metadata=field_options(
            deserialize=datetime.fromtimestamp,
            serialize=lambda v: int(datetime.timestamp(v)),
        )
    )
    expiration_time: datetime = field(
        metadata=field_options(
            deserialize=datetime.fromtimestamp,
            serialize=lambda v: int(datetime.timestamp(v)),
        )
    )
    account_created: bool | None = field(default=None, metadata=field_options(alias="accountCreated"))
    email: str | None = None

    def is_expired(self):
        return datetime.now(tz=timezone.utc) > self.expiration_time.astimezone(tz=timezone.utc)


@dataclass
class SchibstedAuthClientData(BaseDataClassORJSONMixin):
    """Represents Schibsted authentication client data.

    Attributes:
        app_type (str): The type of the application.
        birthday_format (str): The format used for birthdays.
        company (str): The company name.
        css (dict): CSS-related information.
        default_client_id (str): The default client ID.
        domain (str): The domain associated with the client.
        email_receipts_enabled (bool): Indicates if email receipts are enabled.
        id (str): The client's unique identifier.
        locale (str): The locale setting for the client.
        logo_mark_url (str): The URL of the logo mark.
        logo_url (str): The URL of the main logo.
        merchant_id (int): The merchant's unique identifier.
        merchant_name (str): The name of the merchant.
        merchant_type (str): The type of merchant.
        name (str): The name of the client.
        pulse_provider_id (str): The Pulse provider ID.
        session_service_domain (str): The domain for the session service.
        support_url (str): The URL for support.
        terms (dict): Terms-related information.
        uri_scheme (str): The URI scheme used by the client.
        teaser (dict | None): Teaser-related information, if available.

    """

    app_type: str = field(metadata=field_options(alias="appType"))
    birthday_format: str = field(metadata=field_options(alias="birthdayFormat"))
    company: str
    css: dict
    default_client_id: str = field(metadata=field_options(alias="defaultClientId"))
    domain: str
    email_receipts_enabled: bool = field(metadata=field_options(alias="emailReceiptsEnabled"))
    id: str
    locale: str
    logo_mark_url: str = field(metadata=field_options(alias="logoMarkUrl"))
    logo_url: str = field(metadata=field_options(alias="logoUrl"))
    merchant_id: int = field(metadata=field_options(alias="merchantId"))
    merchant_name: str = field(metadata=field_options(alias="merchantName"))
    merchant_type: str = field(metadata=field_options(alias="merchantType"))
    name: str
    pulse_provider_id: str = field(metadata=field_options(alias="pulseProviderId"))
    session_service_domain: str = field(metadata=field_options(alias="sessionServiceDomain"))
    support_url: str = field(metadata=field_options(alias="supportUrl"))
    terms: dict
    uri_scheme: str = field(metadata=field_options(alias="uriScheme"))
    teaser: dict | None = field(default=None)


@dataclass
class PodMeBffData(BaseDataClassORJSONMixin):
    """Represents PodMe Backend-for-Frontend (BFF) data.

    Attributes:
        bff (dict): Backend-for-Frontend related information.
        client (SchibstedAuthClientData): Schibsted authentication client data.
        csrf_token (str): The CSRF token for security.
        default_terms_agreement (bool): Indicates if default terms are agreed to.
        initial_state (dict): The initial state of the application.
        pulse (dict): Pulse-related information.
        re_captcha_site_key (str): The reCAPTCHA site key.
        spid_url (str): The SPiD URL.

    """

    bff: dict
    client: SchibstedAuthClientData
    csrf_token: str = field(metadata=field_options(alias="csrfToken"))
    default_terms_agreement: bool = field(metadata=field_options(alias="defaultTermsAgreement"))
    initial_state: dict = field(metadata=field_options(alias="initialState"))
    pulse: dict
    re_captcha_site_key: str = field(metadata=field_options(alias="reCaptchaSiteKey"))
    spid_url: str = field(metadata=field_options(alias="spidUrl"))
