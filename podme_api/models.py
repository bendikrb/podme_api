"""podme_api models."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum, StrEnum, auto

from mashumaro import field_options
from mashumaro.mixins.orjson import DataClassORJSONMixin


@dataclass
class PodMeCredentials(DataClassORJSONMixin):
    access_token: str
    token_type: str
    expires_in: int
    id_token: str
    refresh_token: str | None = field(default=None, metadata=field_options(alias="refreshToken"))
    scope: str | None = field(default=None, metadata=field_options(alias="scope"))
    user_id: int | None = field(default=None, metadata=field_options(alias="userId"))
    is_admin: bool | None = field(default=None, metadata=field_options(alias="isAdmin"))
    server_time: int | None = field(default=None, metadata=field_options(alias="serverTime"))
    expiration_time: datetime | None = field(default=None, metadata=field_options(alias="expirationTime"))

    @property
    def is_expired(self):
        return False

    @classmethod
    def __pre_deserialize__(cls, d: dict[any, any]) -> dict[any, any]:
        # Convert an empty string to None.
        if not d.get("expiration_time"):
            d["expiration_time"] = None
        return d


class PodMeModels(StrEnum):
    """Enumeration of utilized PodMe models."""

    CATEGORY = auto()
    PODCAST = auto()
    EPISODE = auto()
    SEARCH_RESULT = auto()
    EPISODE_EXCERPT = auto()
    SUBSCRIPTION_PLAN = auto()
    SUBSCRIPTION = auto()


class PodMeLanguage(StrEnum):
    SE = auto()
    NO = auto()
    FI = auto()

    def __repr__(self):
        return self.value.lower()


class PodMeRegion(IntEnum):
    SE = 1
    NO = 2
    FI = 3

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name.lower()

    @property
    def default_language(self):
        return PodMeLanguage[self.name]


@dataclass
class PodMeCategory(DataClassORJSONMixin):
    id: int
    name: str
    key: str
    image_url: str | None = field(default=None, metadata=field_options(alias="imageUrl"))


@dataclass
class PodMePodcastBase(DataClassORJSONMixin):
    id: int
    title: str
    is_premium: bool = field(metadata=field_options(alias="isPremium"))
    small_image_url: str = field(metadata=field_options(alias="smallImageUrl"))
    medium_image_url: str = field(metadata=field_options(alias="mediumImageUrl"))
    large_image_url: str = field(metadata=field_options(alias="largeImageUrl"))
    slug: str


@dataclass
class PodMePodcast(PodMePodcastBase):
    image_url: str | None = field(default=None, metadata=field_options(alias="imageUrl"))
    author_full_name: str | None = field(default=None, metadata=field_options(alias="authorFullName"))
    has_bookmark: bool | None = field(default=None, metadata=field_options(alias="hasBookmark"))
    has_subscription: bool | None = field(default=None, metadata=field_options(alias="hasSubscription"))
    categories: list[PodMeCategory] | None = field(default=None)
    subscription_type: int | None = field(default=None, metadata=field_options(alias="subscriptionType"))
    description: str | None = field(default=None)


@dataclass
class PodMeHomeSectionPodcast(PodMePodcastBase):
    description: str
    destination: str
    categories: list[PodMeCategory] | None = None
    image_url: str | None = field(default=None, metadata=field_options(alias="imageUrl"))


@dataclass
class PodMeHomeSection(DataClassORJSONMixin):
    title: str
    podcasts: list[PodMeHomeSectionPodcast]


@dataclass
class PodMeSearchResult(DataClassORJSONMixin):
    podcast_id: int = field(metadata=field_options(alias="podcastId"))
    podcast_title: str = field(metadata=field_options(alias="podcastTitle"))
    image_url: str = field(metadata=field_options(alias="imageUrl"))
    author_full_name: str = field(metadata=field_options(alias="authorFullName"))
    date_added: datetime = field(metadata=field_options(alias="dateAdded"))
    slug: str
    is_premium: bool = field(metadata=field_options(alias="isPremium"))
    types: list = field(default_factory=list)


@dataclass
class PodMeEpisodeExcerpt(DataClassORJSONMixin):
    id: int
    podcast_id: int = field(metadata=field_options(alias="podcastId"))
    title: str
    length: str
    small_image_url: str = field(metadata=field_options(alias="smallImageUrl"))
    medium_image_url: str = field(metadata=field_options(alias="mediumImageUrl"))
    date_added: datetime = field(metadata=field_options(alias="dateAdded"))
    is_premium: bool = field(metadata=field_options(alias="isPremium"))
    episode_can_be_played: bool = field(metadata=field_options(alias="episodeCanBePlayed"))
    only_as_package_subscription: bool = field(metadata=field_options(alias="onlyAsPackageSubscription"))
    current_spot: str = field(metadata=field_options(alias="currentSpot"))
    description: str | None = field(default=None)

    def __getitem__(self, item):
        return getattr(self, item)


@dataclass
class PodMeEpisode(PodMeEpisodeExcerpt):
    author_full_name: str | None = field(default=None, metadata=field_options(alias="authorFullName"))
    podcast_title: str | None = field(default=None, metadata=field_options(alias="podcastTitle"))
    image_url: str | None = field(default=None, metadata=field_options(alias="imageUrl"))
    slug: str | None = field(default=None)
    stream_url: str | None = field(default=None, metadata=field_options(alias="streamUrl"))
    stream_codec: str | None = field(default=None, metadata=field_options(alias="streamCodec"))


@dataclass
class PodMeSubscriptionPlan(DataClassORJSONMixin):
    name: str
    package_id: int = field(metadata=field_options(alias="packageId"))
    price_decimal: float = field(metadata=field_options(alias="priceDecimal"))
    currency: str
    product_id: str = field(metadata=field_options(alias="productId"))
    plan_guid: str | None = field(default=None, metadata=field_options(alias="planGuid"))
    month_limit: str | None = field(default=None, metadata=field_options(alias="monthLimit"))
    next_plan_id: int | None = field(default=None, metadata=field_options(alias="nextPlanId"))
    next_plan_price_decimal: float | None = field(
        default=None, metadata=field_options(alias="nextPlanPriceDecimal")
    )
    next_plan_product_id: float | None = field(
        default=None, metadata=field_options(alias="nextPlanProductId")
    )
    price: int | None = field(default=None)


@dataclass
class PodMeSubscription(DataClassORJSONMixin):
    subscription_state: int = field(metadata=field_options(alias="subscriptionState"))
    subscription_type: int = field(metadata=field_options(alias="subscriptionType"))
    subscription_platform: int = field(metadata=field_options(alias="subscriptionPlatform"))
    expiration_date: datetime = field(
        metadata=field_options(
            alias="expirationDate",
            deserialize=datetime.fromisoformat,
            serialize=datetime.isoformat,
        )
    )
    start_date: datetime = field(
        metadata=field_options(
            alias="startDate",
            deserialize=datetime.fromisoformat,
            serialize=datetime.isoformat,
        )
    )
    will_be_renewed: bool = field(metadata=field_options(alias="willBeRenewed"))
    subscription_plan: PodMeSubscriptionPlan = field(metadata=field_options(alias="subscriptionPlan"))
    discriminator: str
    reward_month_credit: str | None = field(default=None, metadata=field_options(alias="rewardMonthCredit"))
    image_url: str | None = field(default=None, metadata=field_options(alias="imageUrl"))
    podcast_id: int | None = field(default=None, metadata=field_options(alias="podcastId"))
    podcast_title: str | None = field(default=None, metadata=field_options(alias="podcastTitle"))
