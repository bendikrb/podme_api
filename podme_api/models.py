""""""
from enum import StrEnum, auto
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, ConfigDict, computed_field


class PodMeCredentials(BaseModel):
    model_config = ConfigDict(
        extra='ignore',
        json_encoders={
            datetime: lambda v: v.timestamp(),
        },
    )

    access_token: str
    token_type: str
    expires_in: int
    id_token: str
    refresh_token: Optional[str] = None
    scope: Optional[str] = None
    user_id: Optional[int] = None
    is_admin: Optional[bool] = False
    server_time: Optional[int] = None
    expiration_time: Optional[datetime] = None

    @computed_field(repr=False)
    def is_expired(self) -> bool:
        expiration_time = self.expiration_time or (datetime.now() + timedelta(
            seconds=self.expires_in,
        ))
        return datetime.now().astimezone() > expiration_time.astimezone()

    def auth_header(self):
        return f"{self.token_type} {self.access_token}"


class PodMeModels(StrEnum):
    """Enumeration of utilized PodMe models."""
    CATEGORY = auto()
    PODCAST = auto()
    EPISODE = auto()
    SEARCH_RESULT = auto()
    EPISODE_EXCERPT = auto()
    SUBSCRIPTION_PLAN = auto()
    SUBSCRIPTION = auto()


class PodMeCategory(BaseModel):
    id: int
    name: str
    key: str


class PodMePodcast(BaseModel):
    id: int
    title: str
    isPremium: bool
    smallImageUrl: str
    mediumImageUrl: str
    slug: str
    authorFullName: Optional[str] = None
    hasBookmark: Optional[bool] = None
    hasSubscription: Optional[bool] = None
    categories: Optional[list[PodMeCategory]] = None
    subscriptionType: Optional[int] = None
    description: Optional[str] = None
    imageUrl: Optional[str] = None


class PodMeSearchResult(BaseModel):
    podcastId: int
    podcastTitle: str
    types: list
    imageUrl: str
    authorFullName: str
    dateAdded: datetime
    slug: str
    isPremium: bool


class PodMeEpisodeExcerpt(BaseModel):
    id: int
    podcastId: int
    title: str
    length: str
    smallImageUrl: str
    mediumImageUrl: str
    dateAdded: datetime
    isPremium: bool
    episodeCanBePlayed: bool
    onlyAsPackageSubscription: bool
    currentSpot: str
    description: Optional[str] = None

    def __getitem__(self, item):
        return getattr(self, item)


class PodMeEpisode(PodMeEpisodeExcerpt):
    authorFullName: Optional[str] = None
    podcastTitle: Optional[str] = None
    imageUrl: Optional[str] = None
    slug: Optional[str] = None
    streamUrl: Optional[str] = None


class PodMeSubscriptionPlan(BaseModel):
    name: str
    packageId: int
    price: Optional[int] = None
    priceDecimal: float
    currency: str
    productId: str
    planGuid: Optional[str] = None
    monthLimit: Optional[str] = None
    nextPlanId: Optional[int] = None
    nextPlanPriceDecimal: Optional[float] = None


class PodMeSubscription(BaseModel):
    lastOrderId: str
    subscriptionState: int
    subscriptionType: int
    subscriptionPlatform: int
    expirationDate: datetime
    startDate: datetime
    imageUrl: Optional[str] = None
    willBeRenewed: bool
    subscriptionPlan: Optional[PodMeSubscriptionPlan] = None
    podcastId: Optional[int] = None
    podcastTitle: Optional[str] = None
    discriminator: str
