"""podme_api models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from enum import IntEnum, StrEnum, auto

from mashumaro import field_options
from mashumaro.config import BaseConfig
from mashumaro.mixins.orjson import DataClassORJSONMixin
from mashumaro.types import Discriminator


@dataclass
class BaseDataClassORJSONMixin(DataClassORJSONMixin):
    class Config(BaseConfig):
        omit_none = True
        allow_deserialization_not_by_alias = True


@dataclass
class PodMeCredentials(BaseDataClassORJSONMixin):
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
class PodMeCategory(BaseDataClassORJSONMixin):
    id: int
    name: str
    key: str
    image_url: str | None = field(default=None, metadata=field_options(alias="imageUrl"))


@dataclass
class PodMeCategoryPageSectionContent(BaseDataClassORJSONMixin):
    title: str
    type: str

    class Config(BaseConfig):
        discriminator = Discriminator(
            field="type",
            include_subtypes=True,
        )


@dataclass
class PodMeCategoryPagePodcastCarousel(PodMeCategoryPageSectionContent):
    type = "podcastCarousel"
    podcasts: list[PodMeHomeSectionPodcast]
    is_top_list: bool | None = field(default=None, metadata=field_options(alias="isTopList"))
    show_release_date: bool | None = field(default=None, metadata=field_options(alias="showReleaseDate"))
    destination: str | None = field(default=None, metadata=field_options(alias="destination"))


@dataclass
class PodMeCategoryPagePodcastPromoCarousel(PodMeCategoryPageSectionContent):
    type = "podcastPromoCarousel"
    promoted_podcasts: list[PodMeHomeSectionPodcast] = field(metadata=field_options(alias="promotedPodcasts"))
    is_top_list: bool | None = field(default=None, metadata=field_options(alias="isTopList"))


@dataclass
class PodMeCategoryPageEpisodePromoCarousel(PodMeCategoryPageSectionContent):
    type = "episodePromoCarousel"
    promoted_episodes: list[PodMeHomeSectionEpisode] = field(metadata=field_options(alias="promotedEpisodes"))
    is_top_list: bool | None = field(default=None, metadata=field_options(alias="isTopList"))


@dataclass
class PodMeCategoryPageBannerWithEpisodeList(PodMeCategoryPageSectionContent):
    type = "bannerWithEpisodeList"
    description: str
    hide_title: bool = field(metadata=field_options(alias="hideTitle"))
    image_url: str = field(metadata=field_options(alias="imageUrl"))
    episodes: list[PodMeHomeSectionEpisode]


@dataclass
class PodMeHomeEpisodeList(BaseDataClassORJSONMixin):
    title: str
    type: str
    episodes: list[PodMeHomeSectionEpisode]


@dataclass
class PodMeHomeSectionHeroCard(BaseDataClassORJSONMixin):
    type: str

    class Config(BaseConfig):
        discriminator = Discriminator(
            field="type",
            include_subtypes=True,
        )


@dataclass
class PodMeHomeSectionEpisodeHeroCard(PodMeHomeSectionHeroCard):
    type = "episode"
    podcast_id: int = field(metadata=field_options(alias="podcastId"))
    has_podcast_bookmark: bool = field(metadata=field_options(alias="hasPodcastBookmark"))
    episode_data: PodMeEpisodeData = field(metadata=field_options(alias="episodeData"))
    is_playable: bool = field(metadata=field_options(alias="isPlayable"))
    image_url: str = field(metadata=field_options(alias="imageUrl"))
    destination: str = field(metadata=field_options(alias="destination"))
    destination_path: str = field(metadata=field_options(alias="destinationPath"))
    main_header: str = field(metadata=field_options(alias="mainHeader"))
    short_description: str = field(metadata=field_options(alias="shortDescription"))
    sub_header: str | None = field(default=None, metadata=field_options(alias="subHeader"))


@dataclass
class PodMeCategoryPagePodcastNuggets(PodMeCategoryPageSectionContent):
    type = "podcastNuggets"
    subtitle: str
    episode_lists: list[PodMeHomeEpisodeList] = field(metadata=field_options(alias="episodeLists"))


@dataclass
class PodMeCategoryPageEpisodeCarousel(PodMeCategoryPageSectionContent):
    type = "episodeCarousel"
    episodes: list[PodMeHomeSectionEpisode]


@dataclass
class PodMeSectionHeroCards(PodMeCategoryPageSectionContent):
    type = "listOfHeroCards"
    hero_cards: list[PodMeHomeSectionHeroCard] = field(metadata=field_options(alias="heroCards"))


@dataclass
class PodMeCategoryPageSection(BaseDataClassORJSONMixin):
    content: PodMeCategoryPageSectionContent


@dataclass
class PodMeHomeScreen(BaseDataClassORJSONMixin):
    sections: list[PodMeCategoryPageSection]
    type: str


@dataclass
class PodMeCategoryPage(PodMeHomeScreen):
    title: str
    display_title: str = field(metadata=field_options(alias="displayTitle"))
    description: str


@dataclass
class PodMePodcastBase(BaseDataClassORJSONMixin):
    id: int
    title: str
    is_premium: bool = field(metadata=field_options(alias="isPremium"))
    slug: str
    image_url: str | None = field(default=None, metadata=field_options(alias="imageUrl"))


@dataclass
class PodMePodcast(PodMePodcastBase):
    small_image_url: str | None = field(default=None, metadata=field_options(alias="smallImageUrl"))
    medium_image_url: str | None = field(default=None, metadata=field_options(alias="mediumImageUrl"))
    large_image_url: str | None = field(default=None, metadata=field_options(alias="largeImageUrl"))
    author_id: int | None = field(default=None, metadata=field_options(alias="authorId"))
    author_full_name: str | None = field(default=None, metadata=field_options(alias="authorFullName"))
    has_bookmark: bool | None = field(default=None, metadata=field_options(alias="hasBookmark"))
    has_subscription: bool | None = field(default=None, metadata=field_options(alias="hasSubscription"))
    has_free_options: bool | None = field(default=None, metadata=field_options(alias="hasFreeOptions"))
    has_buy_options: bool | None = field(default=None, metadata=field_options(alias="hasBuyOptions"))
    is_featured: bool | None = field(default=None, metadata=field_options(alias="isFeatured"))
    is_in_spotlight: bool | None = field(default=None, metadata=field_options(alias="isInSpotlight"))
    categories: list[PodMeCategory] | None = field(default=None)
    subscription_type: int | None = field(default=None, metadata=field_options(alias="subscriptionType"))
    description: str | None = None
    only_as_package_subscription: bool | None = field(
        default=None, metadata=field_options(alias="onlyAsPackageSubscription")
    )
    only_as_podcast_subscription: bool | None = field(
        default=None, metadata=field_options(alias="onlyAsPodcastSubscription")
    )
    requires_importing: bool | None = field(default=None, metadata=field_options(alias="requiresImporting"))


@dataclass
class PodMeHomeSectionPodcast(PodMePodcastBase):
    destination: str | None = None
    destination_path: str | None = field(default=None, metadata=field_options(alias="destinationPath"))
    description: str | None = None
    categories: list[PodMeCategory] | None = None


@dataclass
class PodMeHomeSection(BaseDataClassORJSONMixin):
    title: str
    podcasts: list[PodMeHomeSectionPodcast]


@dataclass
class PodMeSearchResult(BaseDataClassORJSONMixin):
    podcast_id: int = field(metadata=field_options(alias="podcastId"))
    podcast_title: str = field(metadata=field_options(alias="podcastTitle"))
    image_url: str = field(metadata=field_options(alias="imageUrl"))
    author_full_name: str = field(metadata=field_options(alias="authorFullName"))
    date_added: datetime = field(metadata=field_options(alias="dateAdded"))
    slug: str
    is_premium: bool = field(metadata=field_options(alias="isPremium"))
    types: list | None = None


@dataclass(kw_only=True)
class PodMeEpisodeBase(BaseDataClassORJSONMixin):
    id: int
    podcast_id: int = field(metadata=field_options(alias="podcastId"))
    title: str
    podcast_title: str = field(metadata=field_options(alias="podcastTitle"))
    length: time = field(
        metadata=field_options(
            deserialize=time.fromisoformat,
            serialize=time.isoformat,
        )
    )
    description: str | None = None
    html_description: str | None = field(default=None, metadata=field_options(alias="htmlDescription"))
    image_url: str | None = field(default=None, metadata=field_options(alias="imageUrl"))
    date_added: datetime = field(metadata=field_options(alias="dateAdded"))
    is_premium: bool = field(metadata=field_options(alias="isPremium"))


@dataclass(kw_only=True)
class PodMeHomeSectionEpisode(PodMeEpisodeBase):
    audio_length: int = field(metadata=field_options(alias="audioLength"))
    is_playable: bool = field(metadata=field_options(alias="isPlayable"))
    podcast_slug: str = field(metadata=field_options(alias="podcastSlug"))
    destination: str | None = None
    destination_path: str | None = field(default=None, metadata=field_options(alias="destinationPath"))


@dataclass(kw_only=True)
class PodMeEpisode(PodMeEpisodeBase):
    author_full_name: str = field(metadata=field_options(alias="authorFullName"))
    small_image_url: str = field(metadata=field_options(alias="smallImageUrl"))
    medium_image_url: str = field(metadata=field_options(alias="mediumImageUrl"))
    stream_url: str | None = field(default=None, metadata=field_options(alias="streamUrl"))
    slug: str | None = None
    current_spot: time = field(
        metadata=field_options(
            alias="currentSpot",
            deserialize=time.fromisoformat,
            serialize=time.isoformat,
        )
    )
    current_spot_sec: int = field(metadata=field_options(alias="currentSpotSec"))
    episode_can_be_played: bool = field(metadata=field_options(alias="episodeCanBePlayed"))
    only_as_package_subscription: bool = field(metadata=field_options(alias="onlyAsPackageSubscription"))
    has_completed: bool = field(metadata=field_options(alias="hasCompleted"))
    is_rss: bool | None = field(default=None, metadata=field_options(alias="isRss"))
    total_no_of_episodes: int | None = field(default=None, metadata=field_options(alias="totalNoOfEpisodes"))


@dataclass
class PodMeEpisodeData(PodMeEpisode):
    number: int = field(metadata=field_options(alias="number"))
    byte_length: int = field(metadata=field_options(alias="byteLength"))
    url: str = field(metadata=field_options(alias="url"))
    type: str = field(metadata=field_options(alias="type"))
    smooth_streaming_url: str = field(metadata=field_options(alias="smoothStreamingUrl"))
    mpeg_dash_url: str = field(metadata=field_options(alias="mpegDashUrl"))
    hls_v3_url: str = field(metadata=field_options(alias="hlsV3Url"))
    hls_v4_url: str = field(metadata=field_options(alias="hlsV4Url"))
    publish_date: datetime = field(metadata=field_options(alias="publishDate"))
    has_played: bool = field(metadata=field_options(alias="hasPlayed"))
    episode_created_at: datetime = field(metadata=field_options(alias="episodeCreatedAt"))
    episode_updated_at: datetime = field(metadata=field_options(alias="episodeUpdatedAt"))
    podcast_image_url: str = field(metadata=field_options(alias="podcastImageUrl"))
    play_info_updated_at: datetime | None = field(
        default=None, metadata=field_options(alias="playInfoUpdatedAt")
    )


@dataclass
class PodMeSubscriptionPlan(BaseDataClassORJSONMixin):
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
class PodMeSubscription(BaseDataClassORJSONMixin):
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
