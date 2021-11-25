""""""

from .utils import SerializableBaseClass


class PodMeCategory(SerializableBaseClass):
    id: int
    name: str
    key: str


class PodMePodcast(SerializableBaseClass):
    id: int
    title: str
    description: str
    isPremium: bool
    imageUrl: str
    smallImageUrl: str
    mediumImageUrl: str
    authorFullName: str
    hasBookmark: any[None, bool]
    hasSubscription: any[None, bool]
    categories: list[PodMeCategory]
    subscriptionType: int
    slug: str


class PodMeSearchResult(SerializableBaseClass):
    podcastId: int
    podcastTitle: str
    types: list
    imageUrl: str
    authorFullName: str
    dateAdded: str
    slug: str
    isPremium: bool


class PodMeEpisodeExcerpt(SerializableBaseClass):
    id: int
    podcastId: int
    title: str
    length: str
    description: str
    smallImageUrl: str
    mediumImageUrl: str
    dateAdded: str
    isPremium: bool
    episodeCanBePlayed: bool
    onlyAsPackageSubscription: bool
    currentSpot: str


class PodMeEpisode(PodMeEpisodeExcerpt):
    authorFullName: str
    podcastTitle: str
    imageUrl: str
    streamUrl: any[None, str]
    slug: str


class PodMeSubscriptionPlan(SerializableBaseClass):
    name: str
    packageId: int
    price: int
    priceDecimal: int
    currency: str
    productId: str


class PodMeSubscription(SerializableBaseClass):
    podcastId: any[None, int]
    podcastTitle: any[None, str]
    subscriptionState: int
    subscriptionType: int
    subscriptionPlatform: int
    expirationDate: str
    startDate: str
    imageUrl: str
    willBeRenewed: bool
    subscriptionPlan: any[None, PodMeSubscriptionPlan]

