"""podme_api models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from enum import IntEnum, StrEnum
from typing import TYPE_CHECKING, TypedDict, TypeVar

from mashumaro import field_options
from mashumaro.config import BaseConfig
from mashumaro.mixins.orjson import DataClassORJSONMixin
from mashumaro.types import Discriminator

if TYPE_CHECKING:
    from yarl import URL


T = TypeVar("T")


@dataclass
class BaseDataClassORJSONMixin(DataClassORJSONMixin):
    class Config(BaseConfig):
        omit_none = True
        allow_deserialization_not_by_alias = True


class PodMeModels(StrEnum):
    """Enumeration of utilized PodMe models."""

    CATEGORY = "CATEGORY"
    PODCAST = "PODCAST"
    EPISODE = "EPISODE"
    SEARCH_RESULT = "SEARCH_RESULT"
    EPISODE_EXCERPT = "EPISODE_EXCERPT"
    SUBSCRIPTION_PLAN = "SUBSCRIPTION_PLAN"
    SUBSCRIPTION = "SUBSCRIPTION"


class PodMeLanguage(StrEnum):
    """Enumeration of supported PodMe languages."""

    SE = "SE"
    NO = "NO"
    FI = "FI"

    def __repr__(self):
        return self.value.lower()


class PodMeRegion(IntEnum):
    """Enumeration of PodMe regions."""

    SE = 1
    NO = 2
    FI = 3
    DK = 4

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name.lower()

    @property
    def default_language(self):  # pragma: no cover
        """Get the default language for the region."""
        return PodMeLanguage[self.name]


class PodMeLoginType(IntEnum):
    """Enumeration of PodMe login types."""

    PODME_ACCOUNT = 0
    APPLE = 1
    GOOGLE = 2
    FACEBOOK = 3
    SCHIBSTED_SE = 4
    SCHIBSTED_FI = 5
    SCHIBSTED_NO = 6


class PodMeSortModeSavedList(IntEnum):
    """Enumeration of SortModeSavedList."""

    LATEST_ADDED = 0
    OLDEST_ADDED = 1
    LATEST_RELEASED = 2
    OLDEST_RELEASED = 3


class PodMeDownloadProgressTask(StrEnum):
    """Enumeration of PodMe download progress tasks."""

    INITIALIZE = "INITIALIZE"
    RESOLVE_URL = "RESOLVE_URL"
    DOWNLOAD_FILE = "DOWNLOAD_FILE"
    TRANSCODE_FILE = "TRANSCODE_FILE"
    COMPLETE = "COMPLETE"


@dataclass
class PodMeCategory(BaseDataClassORJSONMixin):
    """Represents a PodMe category."""

    id: int
    name: str
    key: str
    image_url: str | None = field(default=None, metadata=field_options(alias="imageUrl"))


@dataclass
class PodMeCategoryPageSectionContent(BaseDataClassORJSONMixin):
    """Base class for PodMe category page section content."""

    title: str
    type: str

    class Config(BaseConfig):
        discriminator = Discriminator(
            field="type",
            include_subtypes=True,
        )


@dataclass
class PodMeCategoryPagePodcastCarousel(PodMeCategoryPageSectionContent):
    """Represents a podcast carousel in a PodMe category page section."""

    type = "podcastCarousel"
    podcasts: list[PodMeHomeSectionPodcast]
    is_top_list: bool | None = field(default=None, metadata=field_options(alias="isTopList"))
    show_release_date: bool | None = field(default=None, metadata=field_options(alias="showReleaseDate"))
    destination: str | None = field(default=None, metadata=field_options(alias="destination"))


@dataclass
class PodMeCategoryPagePodcastPromoCarousel(PodMeCategoryPageSectionContent):
    """Represents a podcast promo carousel in a PodMe category page section."""

    type = "podcastPromoCarousel"
    promoted_podcasts: list[PodMeHomeSectionPodcast] = field(metadata=field_options(alias="promotedPodcasts"))
    is_top_list: bool | None = field(default=None, metadata=field_options(alias="isTopList"))


@dataclass
class PodMeCategoryPageEpisodePromoCarousel(PodMeCategoryPageSectionContent):
    """Represents an episode promo carousel in a PodMe category page section."""

    type = "episodePromoCarousel"
    promoted_episodes: list[PodMeHomeSectionEpisode] = field(metadata=field_options(alias="promotedEpisodes"))
    is_top_list: bool | None = field(default=None, metadata=field_options(alias="isTopList"))


@dataclass
class PodMeCategoryPageBannerWithEpisodeList(PodMeCategoryPageSectionContent):
    """Represents a banner with episode list in a PodMe category page section."""

    type = "bannerWithEpisodeList"
    description: str
    hide_title: bool = field(metadata=field_options(alias="hideTitle"))
    image_url: str = field(metadata=field_options(alias="imageUrl"))
    episodes: list[PodMeHomeSectionEpisode]


@dataclass
class PodMeHomeEpisodeList(BaseDataClassORJSONMixin):
    """Represents a list of episodes in the PodMe home screen."""

    title: str
    type: str
    episodes: list[PodMeHomeSectionEpisode]


@dataclass
class PodMeHomeSectionHeroCard(BaseDataClassORJSONMixin):
    """Base class for PodMe home section hero cards."""

    type: str

    class Config(BaseConfig):
        discriminator = Discriminator(
            field="type",
            include_subtypes=True,
        )


@dataclass
class PodMeHomeSectionEpisodeHeroCard(PodMeHomeSectionHeroCard):
    """Represents an episode hero card in a PodMe home section."""

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
    """Represents podcast nuggets in a PodMe category page section."""

    type = "podcastNuggets"
    subtitle: str
    episode_lists: list[PodMeHomeEpisodeList] = field(metadata=field_options(alias="episodeLists"))


@dataclass
class PodMeCategoryPageEpisodeCarousel(PodMeCategoryPageSectionContent):
    """Represents an episode carousel in a PodMe category page section."""

    type = "episodeCarousel"
    episodes: list[PodMeHomeSectionEpisode]


@dataclass
class PodMeSectionHeroCards(PodMeCategoryPageSectionContent):
    """Represents a list of hero cards in a PodMe section."""

    type = "listOfHeroCards"
    hero_cards: list[PodMeHomeSectionHeroCard] = field(metadata=field_options(alias="heroCards"))


@dataclass
class PodMeCategoryPageSection(BaseDataClassORJSONMixin):
    """Represents a section in a PodMe category page."""

    content: PodMeCategoryPageSectionContent


@dataclass
class PodMeHomeScreen(BaseDataClassORJSONMixin):
    """Represents the PodMe home screen."""

    sections: list[PodMeCategoryPageSection]
    type: str


@dataclass
class PodMeCategoryPage(PodMeHomeScreen):
    """Represents a PodMe category page."""

    title: str
    display_title: str = field(metadata=field_options(alias="displayTitle"))
    description: str


@dataclass
class PodMePodcastBase(BaseDataClassORJSONMixin):
    """Base class for PodMe podcasts."""

    id: int
    title: str
    is_premium: bool = field(metadata=field_options(alias="isPremium"))
    slug: str
    image_url: str | None = field(default=None, metadata=field_options(alias="imageUrl"))

    @classmethod
    def from_search_result(cls: type[T], data: dict) -> T:
        search_result = PodMeSearchResult.from_dict(data)
        return PodMePodcastBase.from_dict(
            {
                "id": search_result.podcast_id,
                "title": search_result.podcast_title,
                "is_premium": search_result.is_premium,
                "slug": search_result.slug,
                "image_url": search_result.image_url,
            }
        )


@dataclass
class PodMePodcast(PodMePodcastBase):
    """Represents a PodMe podcast with extended information."""

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
    """Represents a podcast in a PodMe home section."""

    destination: str | None = None
    destination_path: str | None = field(default=None, metadata=field_options(alias="destinationPath"))
    description: str | None = None
    categories: list[PodMeCategory] | None = None


@dataclass
class PodMeHomeSection(BaseDataClassORJSONMixin):
    """Represents a section in the PodMe home screen."""

    title: str
    podcasts: list[PodMeHomeSectionPodcast]


@dataclass
class PodMeSearchResult(BaseDataClassORJSONMixin):
    """Represents a search result in PodMe."""

    podcast_id: int | str = field(metadata=field_options(alias="podcastId"))
    podcast_title: str = field(metadata=field_options(alias="podcastTitle"))
    image_url: str = field(metadata=field_options(alias="imageUrl"))
    author_full_name: str = field(metadata=field_options(alias="authorFullName"))
    date_added: datetime = field(metadata=field_options(alias="dateAdded"))
    slug: str
    is_premium: bool = field(metadata=field_options(alias="isPremium"))
    types: list | None = None


@dataclass(kw_only=True)
class PodMeEpisodeBase(BaseDataClassORJSONMixin):
    """Base class for PodMe episodes."""

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
    """Represents an episode in a PodMe home section."""

    audio_length: int = field(metadata=field_options(alias="audioLength"))
    is_playable: bool = field(metadata=field_options(alias="isPlayable"))
    podcast_slug: str = field(metadata=field_options(alias="podcastSlug"))
    destination: str | None = None
    destination_path: str | None = field(default=None, metadata=field_options(alias="destinationPath"))


@dataclass(kw_only=True)
class PodMeEpisode(PodMeEpisodeBase):
    """Represents a PodMe episode with extended information."""

    author_full_name: str = field(metadata=field_options(alias="authorFullName"))
    small_image_url: str = field(metadata=field_options(alias="smallImageUrl"))
    medium_image_url: str = field(metadata=field_options(alias="mediumImageUrl"))
    stream_url: str | None = field(default=None, metadata=field_options(alias="streamUrl"))
    slug: str | None = None
    current_spot: time | None = field(
        default=None,
        metadata=field_options(
            alias="currentSpot",
            deserialize=time.fromisoformat,
            serialize=time.isoformat,
        ),
    )
    current_spot_sec: int | None = field(default=None, metadata=field_options(alias="currentSpotSec"))
    episode_can_be_played: bool | None = field(
        default=None, metadata=field_options(alias="episodeCanBePlayed")
    )
    only_as_package_subscription: bool = field(metadata=field_options(alias="onlyAsPackageSubscription"))
    has_completed: bool | None = field(default=None, metadata=field_options(alias="hasCompleted"))
    is_rss: bool | None = field(default=None, metadata=field_options(alias="isRss"))
    total_no_of_episodes: int | None = field(default=None, metadata=field_options(alias="totalNoOfEpisodes"))


@dataclass
class PodMeEpisodeData(PodMeEpisode):
    """Represents detailed data for a PodMe episode."""

    number: int | None = field(default=None, metadata=field_options(alias="number"))
    byte_length: int | None = field(default=None, metadata=field_options(alias="byteLength"))
    url: str | None = field(default=None, metadata=field_options(alias="url"))
    type: str | None = field(default=None, metadata=field_options(alias="type"))
    smooth_streaming_url: str | None = field(default=None, metadata=field_options(alias="smoothStreamingUrl"))
    mpeg_dash_url: str | None = field(default=None, metadata=field_options(alias="mpegDashUrl"))
    hls_v3_url: str | None = field(default=None, metadata=field_options(alias="hlsV3Url"))
    hls_v4_url: str | None = field(default=None, metadata=field_options(alias="hlsV4Url"))
    publish_date: datetime | None = field(default=None, metadata=field_options(alias="publishDate"))
    has_played: bool | None = field(default=None, metadata=field_options(alias="hasPlayed"))
    episode_created_at: datetime | None = field(
        default=None, metadata=field_options(alias="episodeCreatedAt")
    )
    episode_updated_at: datetime | None = field(
        default=None, metadata=field_options(alias="episodeUpdatedAt")
    )
    podcast_image_url: str | None = field(default=None, metadata=field_options(alias="podcastImageUrl"))
    play_info_updated_at: datetime | None = field(
        default=None, metadata=field_options(alias="playInfoUpdatedAt")
    )

    @classmethod
    def __pre_deserialize__(cls: type[T], d: T) -> T:
        for key in ["url", "streamUrl", "smoothStreamingUrl", "mpegDashUrl", "hlsV3Url", "hlsV4Url"]:
            val = d.get(key)
            d[key] = None if val == "" else val
        return d


@dataclass
class PodMeUserPrivacySettings(BaseDataClassORJSONMixin):
    """Represents privacy settings for a PodMe user."""

    has_opted_out_from_targeted_advertising: bool = field(
        metadata=field_options(alias="hasOptedOutFromTargetedAdvertising")
    )
    has_opted_out_from_personalized_news: bool = field(
        metadata=field_options(alias="hasOptedOutFromPersonalizedNews")
    )
    has_opted_out_from_analytics_and_product_development: bool = field(
        metadata=field_options(alias="hasOptedOutFromAnalyticsAndProductDevelopment")
    )
    has_opted_out_from_marketing_3_rd_party_platforms: bool = field(
        metadata=field_options(alias="hasOptedOutFromMarketing3RdPartyPlatforms")
    )


@dataclass
class PodMeUser(BaseDataClassORJSONMixin):
    """Represents a PodMe user."""

    user_id: str = field(metadata=field_options(alias="userId"))
    user_account_id: str = field(metadata=field_options(alias="userAccountId"))
    email: str
    region: PodMeRegion
    login_type: int = field(metadata=field_options(alias="loginType"))
    is_user_schibsted: bool = field(metadata=field_options(alias="isUserSchibsted"))
    is_user_account_schibsted: bool = field(metadata=field_options(alias="isUserAccountSchibsted"))
    is_premium_user: bool = field(metadata=field_options(alias="isPremiumUser"))
    subscription_platform: int = field(metadata=field_options(alias="subscriptionPlatform"))
    has_given_consent_to_marketing_cookies: bool = field(
        metadata=field_options(alias="hasGivenConsentToMarketingCookies")
    )
    has_given_consent_to_analytics_cookies: bool = field(
        metadata=field_options(alias="hasGivenConsentToAnalyticsCookies")
    )
    privacy_settings: PodMeUserPrivacySettings = field(metadata=field_options(alias="privacySettings"))
    consent_given_at: datetime | None = field(
        default=None,
        metadata=field_options(
            alias="consentGivenAt",
            deserialize=datetime.fromisoformat,
            serialize=datetime.isoformat,
        ),
    )


@dataclass
class PodMeSubscriptionPlan(BaseDataClassORJSONMixin):
    """Represents a PodMe subscription plan."""

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
    region_id: int | None = field(default=None, metadata=field_options(alias="regionId"))


@dataclass(kw_only=True)
class PodMeSubscription(BaseDataClassORJSONMixin):
    """Represents a PodMe subscription."""

    subscription_id: int | None = field(default=None, metadata=field_options(alias="subscriptionId"))
    subscription_type: int | None = field(default=None, metadata=field_options(alias="subscriptionType"))
    subscription_state: int = field(metadata=field_options(alias="subscriptionState"))
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
    subscription_plan: PodMeSubscriptionPlan | None = field(
        default=None, metadata=field_options(alias="subscriptionPlan")
    )
    discriminator: str | None = None
    reward_month_credit: str | None = field(default=None, metadata=field_options(alias="rewardMonthCredit"))
    image_url: str | None = field(default=None, metadata=field_options(alias="imageUrl"))
    podcast_id: int | None = field(default=None, metadata=field_options(alias="podcastId"))
    podcast_title: str | None = field(default=None, metadata=field_options(alias="podcastTitle"))
    amount: float | None = None


@dataclass
class PodMeSubscriptions(BaseDataClassORJSONMixin):
    """Represents subscriptions for a PodMe user."""

    has_access: bool = field(metadata=field_options(alias="hasAccess"))
    adyen_subscriptions: list[PodMeSubscription] = field(metadata=field_options(alias="adyenSubscriptions"))
    apple_subscriptions: list[PodMeSubscription] = field(metadata=field_options(alias="appleSubscriptions"))
    google_subscriptions: list[PodMeSubscription] = field(metadata=field_options(alias="googleSubscriptions"))
    schibsted_subscription: PodMeSubscription | None = field(
        default=None, metadata=field_options(alias="schibstedSubscription")
    )


class FetchedFileInfo(TypedDict):
    """Fetched file info."""

    content_length: int
    content_type: str | None
    url: URL
