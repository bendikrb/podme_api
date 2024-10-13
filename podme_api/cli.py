"""podme_api cli tool."""

import argparse
import asyncio
import contextlib
import logging

from rich.console import Console
from rich.logging import RichHandler

from podme_api.auth import PodMeDefaultAuthClient
from podme_api.auth.models import PodMeUserCredentials
from podme_api.client import PodMeClient

console = Console()


def main_parser() -> argparse.ArgumentParser:
    """Create the ArgumentParser with all relevant subparsers."""
    parser = argparse.ArgumentParser(description="A simple executable to use and test the library.")
    _add_default_arguments(parser)

    subparsers = parser.add_subparsers(dest="cmd")
    subparsers.required = True

    subscription_parser = subparsers.add_parser(
        "subscription", description="Get your current PodMe subscription."
    )
    subscription_parser.set_defaults(func=get_subscription)

    categories_parser = subparsers.add_parser("categories", description="Get a list of PodMe categories.")
    categories_parser.set_defaults(func=get_categories)

    favourites_parser = subparsers.add_parser(
        "favourites", description="Get a list of your favourite podcasts."
    )
    favourites_parser.set_defaults(func=get_favourites)

    popular_parser = subparsers.add_parser(
        "popular", description="Get a list of PodMe's most popular podcasts."
    )
    _add_paging_arguments(popular_parser)
    popular_parser.add_argument("--category", help="(optional) Limit by category", nargs="?", default=None)
    popular_parser.add_argument(
        "--type", help="(optional, default=2) Limit by podcast type", nargs="?", default=None
    )
    popular_parser.set_defaults(func=get_popular)

    return parser


async def get_subscription(args) -> None:
    """Retrieve PodMe subscription."""
    async with _get_client(args) as client:
        subscriptions = await client.get_user_subscription()
        for s in subscriptions:
            console.print(s)


async def get_categories(args) -> None:
    async with _get_client(args) as client:
        categories = await client.get_categories()
        for c in categories:
            console.print(c)


async def get_favourites(args) -> None:
    """Retrieve user favourite podcasts."""
    async with _get_client(args) as client:
        podcasts = await client.get_user_podcasts()
        for p in podcasts:
            console.print(p)


async def get_popular(args) -> None:
    """Retrieve favourite podcasts."""
    async with _get_client(args) as client:
        podcasts = await client.get_popular_podcasts(
            page_size=args.per_page,
            pages=args.pages,
            category=args.category,
            podcast_type=args.type,
        )
        for p in podcasts:
            console.print(p)


def _add_default_arguments(parser: argparse.ArgumentParser):
    """Add the default arguments username, password, region to the parser."""
    parser.add_argument(
        "--credentials",
        "-c",
        type=argparse.FileType(),
        default=None,
        help="Path to credentials to load. Defaults to ~/.config/podme_api/credentials.json",
    )
    parser.add_argument("--username", "-u", help="PodMe.com username")
    parser.add_argument("--password", "-p", help="PodMe.com password")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Logging verbosity level")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")


def _add_paging_arguments(parser: argparse.ArgumentParser):
    """Add paging options to the parser."""
    parser.add_argument(
        "pages",
        type=int,
        nargs="?",
        default=1,
        help="(optional) Maximum number of pages to fetch (default=1)",
    )
    parser.add_argument(
        "per_page", type=int, nargs="?", default=25, help="(optional) Number of results per page (default=25)"
    )


@contextlib.asynccontextmanager
async def _get_client(args) -> PodMeClient:
    """Return PodMeClient based on args."""
    if args.username and args.password:
        user_creds = PodMeUserCredentials(args.username, args.password)
    else:
        user_creds = None
    auth_client = PodMeDefaultAuthClient(user_credentials=user_creds)
    client = PodMeClient(auth_client=auth_client)
    try:
        await client.__aenter__()
        yield client
    finally:
        await client.__aexit__(None, None, None)


def main():
    """Run."""
    parser = main_parser()
    args = parser.parse_args()

    if args.debug:
        logging_level = logging.DEBUG
    elif args.verbose:
        logging_level = 50 - (args.verbose * 10)
        if logging_level <= 0:
            logging_level = logging.NOTSET
    else:
        logging_level = logging.ERROR

    logging.basicConfig(
        level=logging_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console)],
    )

    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
