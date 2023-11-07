import argparse
import logging

from rich import print as rprint
from podme_api.client import PodMeClient, PodMeSchibstedClient


def main_parser() -> argparse.ArgumentParser:
    """Creates the ArgumentParser with all relevant subparsers."""
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser(description='A simple executable to use and test the library.')
    _add_default_arguments(parser)

    subparsers = parser.add_subparsers(dest='cmd')
    subparsers.required = True

    subscription_parser = subparsers.add_parser('subscription', description='Get your current PodMe subscription.')

    favourites_parser = subparsers.add_parser('favourites', description='Get a list of your favourite podcasts.')
    favourites_parser.set_defaults(func=get_favourites)

    popular_parser = subparsers.add_parser('popular', description='Get a list of PodMe\'s most popular podcasts.')
    _add_paging_arguments(popular_parser)
    popular_parser.add_argument('--category', help='(optional) Limit by category', nargs='?', default=None)
    popular_parser.add_argument('--type', help='(optional, default=2) Limit by podcast type', nargs='?', default=None)
    popular_parser.set_defaults(func=get_popular)

    return parser


def get_subscription(args) -> None:
    """Retrieve PodMe subscription."""
    client = _get_client(args)

    subscriptions = client.get_user_subscription()
    for s in subscriptions:
        rprint(s)
    # print(dump_podme_object(subscriptions))
    # print(json.dumps(subscription, indent=4))


def get_favourites(args) -> None:
    """Retrieve user favourite podcasts """
    client = _get_client(args)
    podcasts = client.get_user_podcasts()

    for p in podcasts:
        rprint(p)


def get_popular(args) -> None:
    """Retrieve favourite podcasts """
    client = _get_client(args)
    podcasts = client.get_popular_podcasts(
        page_size=args.per_page,
        pages=args.pages,
        category=args.category,
        podcast_type=args.type,
    )

    for p in podcasts:
        print("{id} {title}".format(
            id=f"{p.id}{'*' if p.isPremium else ' '}".rjust(6),
            title=p.title,
        ))

    print('')
    print(' * = Premium')


def _add_default_arguments(parser: argparse.ArgumentParser):
    """Add the default arguments username, password, region to the parser."""
    parser.add_argument('--schibsted', '-s', action='store_true', help='Login using schibsted SSO')
    parser.add_argument('--load_credentials', '-l', action='store_true', help='Load credentials from file')
    parser.add_argument('--username', '-u', help='PodMe.com username')
    parser.add_argument('--password', '-p', help='PodMe.com password')
    parser.set_defaults(func=get_subscription)


def _add_paging_arguments(parser: argparse.ArgumentParser):
    """Add paging options to the parser."""
    parser.add_argument('pages', type=int, nargs='?', default=1,
                        help='(optional) Maximum number of pages to fetch (default=1)')
    parser.add_argument('per_page', type=int, nargs='?', default=25,
                        help='(optional) Number of results per page (default=25)')


def _get_client(args) -> PodMeClient:
    """Return PodMeClient based on args"""
    if args.schibsted:
        client = PodMeSchibstedClient(args.username, args.password)
    else:
        client = PodMeClient(args.username, args.password)

    if client and args.load_credentials:
        client.load_credentials()
    return client


def main():
    """Main function."""
    parser = main_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
