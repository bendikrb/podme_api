"""podme_api cli tool."""

import argparse
import asyncio
from collections.abc import AsyncGenerator
import contextlib
import logging

from rich.console import Console
from rich.live import Live
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from podme_api.__version__ import __version__
from podme_api.auth import PodMeDefaultAuthClient
from podme_api.auth.models import PodMeUserCredentials
from podme_api.cli.utils import bold_star, is_valid_writable_dir, pretty_dataclass, pretty_dataclass_list
from podme_api.client import PodMeClient
from podme_api.models import PodMeDownloadProgressTask

console = Console()


def main_parser() -> argparse.ArgumentParser:
    """Create the ArgumentParser with all relevant subparsers."""
    parser = argparse.ArgumentParser(description="A simple executable to use and test the library.")
    _add_default_arguments(parser)

    subparsers = parser.add_subparsers(dest="cmd")
    subparsers.required = True

    #
    # Login
    #
    login_parser = subparsers.add_parser("login", description="Log in")
    login_parser.add_argument("username", type=str, help="Username / E-mail")
    login_parser.add_argument("password", type=str, help="Password")
    login_parser.set_defaults(func=login)

    #
    # Subscription
    #
    subscription_parser = subparsers.add_parser(
        "subscription", description="Get your current PodMe subscription."
    )
    subscription_parser.set_defaults(func=get_subscription)

    #
    # Favourites
    #
    favourites_parser = subparsers.add_parser(
        "favourites", description="Get a list of your favourite podcasts."
    )
    favourites_parser.set_defaults(func=get_favourites)

    #
    # Podcasts
    #
    podcast_parser = subparsers.add_parser("podcast", description="Get podcast(s).")
    podcast_parser.add_argument("podcast_slug", type=str, nargs="+", help="Podcast slug(s).")
    podcast_parser.add_argument("--episodes", action="store_true", help="Get episodes.")
    _add_paging_arguments(podcast_parser)
    podcast_parser.set_defaults(func=get_podcasts)

    #
    # Episodes
    #
    episode_parser = subparsers.add_parser("episode", description="Get episode(s).")
    episode_parser.add_argument("episode_id", type=int, nargs="+", help="Episode id(s).")
    episode_parser.add_argument("-d", "--download", action="store_true", help="Download episode(s).")
    episode_parser.add_argument(
        "-o",
        dest="output_dir",
        help="Directory to download episode(s) to.",
        metavar="OUTPUT_DIR",
        type=lambda x: is_valid_writable_dir(parser, x),
    )
    episode_parser.set_defaults(func=get_episodes)

    #
    # Categories
    #
    categories_parser = subparsers.add_parser("categories", description="Get a list of PodMe categories.")
    categories_parser.set_defaults(func=get_categories)

    #
    # Popular
    #
    popular_parser = subparsers.add_parser(
        "popular", description="Get a list of PodMe's most popular podcasts."
    )
    _add_paging_arguments(popular_parser)
    popular_parser.add_argument("--category", help="(optional) Limit by category", nargs="?", default=None)
    popular_parser.add_argument(
        "--type", help="(optional, default=2) Limit by podcast type", nargs="?", default=None
    )
    popular_parser.set_defaults(func=get_popular)

    #
    # Search
    #
    search_parser = subparsers.add_parser("search", description="Search.")
    search_parser.add_argument("query", type=str, help="Search query.")
    search_parser.set_defaults(func=search)
    _add_paging_arguments(search_parser)

    return parser


def _add_default_arguments(parser: argparse.ArgumentParser):
    """Add default arguments to the parser."""
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s v{__version__}")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Logging verbosity level")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")


def _add_paging_arguments(parser: argparse.ArgumentParser):
    """Add paging options to the parser."""
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of results to return per page (default=20).",
    )
    parser.add_argument("--pages", type=int, default=1, help="Maxium number of pages to fetch (default=1)")


async def login(args):
    """Login."""
    async with _get_client(args) as client:
        client.auth_client.invalidate_credentials()
        username = await client.get_username()
        console.print(f"Logged in as {username}")


async def get_subscription(args) -> None:
    """Retrieve PodMe subscription."""
    async with _get_client(args) as client:
        subscriptions = await client.get_user_subscription()
        for s in subscriptions:
            console.print(
                *[
                    pretty_dataclass(
                        s,
                        visible_fields=[
                            "expiration_date",
                            "start_date",
                            "will_be_renewed",
                        ],
                    ),
                    pretty_dataclass(
                        s.subscription_plan,
                        visible_fields=[
                            "name",
                            "price_decimal",
                            "currency",
                            "plan_guid",
                        ],
                    ),
                ],
            )


async def get_favourites(args) -> None:
    """Retrieve user favourite podcasts."""
    async with _get_client(args) as client:
        podcasts = await client.get_user_podcasts()
        console.print(
            pretty_dataclass_list(
                podcasts,
                visible_fields=[
                    "id",
                    "slug",
                    "title",
                    "categories",
                ],
                field_formatters={
                    "title": lambda t, obj: f"{bold_star(obj.is_premium)}{t}",
                    "categories": lambda v, _: ", ".join([c.name for c in v]),
                },
                field_order=[
                    "title",
                    "slug",
                    "id",
                    "categories",
                ],
            )
        )


async def get_podcasts(args) -> None:
    async with _get_client(args) as client:
        console.print(f"{args.podcast_slug}")
        podcasts = await client.get_podcasts_info(args.podcast_slug)

        console.print(
            pretty_dataclass_list(
                podcasts,
                visible_fields=[
                    "id",
                    "slug",
                    "title",
                    "categories",
                ],
                field_formatters={
                    "title": lambda t, obj: f"{bold_star(obj.is_premium)}{t}",
                    "categories": lambda v, _: ", ".join([c.name for c in v]),
                },
                field_order=[
                    "title",
                    "slug",
                    "id",
                    "categories",
                ],
            )
        )
        if args.episodes:
            for podcast in podcasts:
                episodes = await client.get_latest_episodes(podcast.slug, episodes_limit=args.limit)
                console.print(
                    pretty_dataclass_list(
                        episodes,
                        title=f"Latest episodes of {podcast.title}",
                        visible_fields=[
                            "id",
                            "title",
                            "date_added",
                            "length",
                        ],
                        field_formatters={
                            "title": lambda t, obj: f"{bold_star(obj.is_premium)}{t}",
                        },
                        field_order=[
                            "id",
                            "title",
                            "length",
                            "date_added",
                        ],
                    )
                )


async def get_episodes(args) -> None:
    async with _get_client(args) as client:
        episodes = await client.get_episodes_info(args.episode_id)
        for episode in episodes:
            console.print(
                pretty_dataclass(
                    episode,
                    title=f"{episode.podcast_title} - {episode.title}",
                    hidden_fields=[
                        "current_spot",
                        "current_spot_sec",
                        "has_completed",
                    ],
                )
            )
        if args.download:
            if not args.output_dir:
                console.print("[red]Please specify an output directory[/red]")
                return
            output_path = args.output_dir
            console.print(f"Downloading to: {output_path} ...")
            ids = [e.id for e in episodes]

            job_progress = Progress(
                "{task.description}",
                SpinnerColumn(),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TextColumn("{task.fields[step]}"),
            )
            overall_progress = Progress(
                TimeElapsedColumn(),
                TextColumn("{task.description}"),
            )
            overall_task_id = overall_progress.add_task("", total=len(ids))

            progress_table = Table.grid()
            progress_table.add_row(overall_progress)
            progress_table.add_row(
                Panel.fit(job_progress, title="[b]Episodes", border_style="red", padding=(1, 2)),
            )

            with Live(progress_table, console=console, refresh_per_second=10):
                overall_progress.update(overall_task_id, description="Preparing download urls")
                download_infos = []
                download_tasks = {}
                downloads = await client.get_episode_download_url_bulk(ids)
                for episode_id, download_url in downloads:
                    path = output_path / f"episode_{episode_id}.mp3"
                    download_infos.append((download_url, path))
                    download_tasks[str(download_url)] = job_progress.add_task(
                        f"Episode {episode_id}",
                        url=download_url,
                        save_path=path,
                        episode_id=episode_id,
                        step="Starting",
                    )

                def on_progress(task: PodMeDownloadProgressTask, url: str, current: int, total: int):
                    progress_task_id = download_tasks[url]
                    percentage = float((current / total) * 100) if total else 0
                    task_friendly_name = {
                        PodMeDownloadProgressTask.INITIALIZE: "Starting",
                        PodMeDownloadProgressTask.DOWNLOAD_FILE: "Downloading",
                        PodMeDownloadProgressTask.TRANSCODE_FILE: "Transcoding",
                    }
                    job_progress.update(progress_task_id, step=task_friendly_name[task], completed=percentage)

                def on_finished(url: str, saved_filename: str):
                    progress_task_id = download_tasks[url]
                    job_progress.update(progress_task_id, step=f"Finished: {saved_filename}", completed=100)
                    overall_progress.update(overall_task_id, advance=1)

                overall_progress.update(overall_task_id, description="Downloading/processing files")

                await client.download_files(download_infos, on_progress, on_finished)

                overall_progress.update(overall_task_id, description="[bold green]Completed")
                await asyncio.sleep(1)


async def get_categories(args) -> None:
    async with _get_client(args) as client:
        categories = await client.get_categories()
        console.print(
            pretty_dataclass_list(
                categories,
                visible_fields=[
                    "id",
                    "key",
                    "name",
                ],
                field_order=["id", "key", "name"],
            ),
        )


async def get_popular(args) -> None:
    """Retrieve favourite podcasts."""
    async with _get_client(args) as client:
        podcasts = await client.get_popular_podcasts(
            page_size=args.limit,
            pages=args.pages,
            category=args.category,
            podcast_type=args.type,
        )
        console.print(
            pretty_dataclass_list(
                podcasts,
                field_formatters={
                    "title": lambda t, obj: f"{bold_star(obj.is_premium)}{t}",
                },
                hidden_fields=[
                    "is_premium",
                    "image_url",
                ],
            )
        )


async def search(args) -> None:
    async with _get_client(args) as client:
        results = await client.search_podcast(
            args.query,
            page_size=args.limit,
            pages=args.pages,
        )
        console.print(
            pretty_dataclass_list(
                results,
                visible_fields=[
                    "podcast_id",
                    "slug",
                    "podcast_title",
                    "author_full_name",
                    "date_added",
                ],
                field_formatters={
                    "podcast_title": lambda t, obj: f"{bold_star(obj.is_premium)}{t}",
                },
                field_order=[
                    "podcast_id",
                    "slug",
                    "podcast_title",
                    "author_full_name",
                    "date_added",
                ],
            )
        )


@contextlib.asynccontextmanager
async def _get_client(args) -> AsyncGenerator[PodMeClient, None]:
    """Return PodMeClient based on args."""
    if hasattr(args, "username") and hasattr(args, "password"):
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
