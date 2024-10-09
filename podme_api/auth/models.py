from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from mashumaro import field_options
from mashumaro.mixins.orjson import DataClassORJSONMixin


@dataclass
class PodMeUserCredentials:
    email: str
    password: str


@dataclass
class SchibstedCredentials(DataClassORJSONMixin):
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
class SchibstedAuthClientData(DataClassORJSONMixin):
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
class PodMeBffData(DataClassORJSONMixin):
    bff: dict
    client: SchibstedAuthClientData
    csrf_token: str = field(metadata=field_options(alias="csrfToken"))
    default_terms_agreement: bool = field(metadata=field_options(alias="defaultTermsAgreement"))
    initial_state: dict = field(metadata=field_options(alias="initialState"))
    pulse: dict
    re_captcha_site_key: str = field(metadata=field_options(alias="reCaptchaSiteKey"))
    spid_url: str = field(metadata=field_options(alias="spidUrl"))
