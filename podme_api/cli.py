import logging
import argparse
import json

from .client import PodMeClient


def main_parser() -> argparse.ArgumentParser:
    """Creates the ArgumentParser with all relevant subparsers."""
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser(description='A simple executable to use and test the library.')
    subparsers = parser.add_subparsers(dest='cmd')
    subparsers.required = True

    subscription_parser = subparsers.add_parser('subscription', description='Get your current PodMe subscription.')
    _add_default_arguments(subscription_parser)

    return parser


def get_subscription(args) -> None:
    """Retrieve PodMe subscription."""
    client = PodMeClient(args.username, args.password)
    
    subscription = client.get_user_subscription()

    print(json.dumps(subscription, indent=4))


def _add_default_arguments(parser: argparse.ArgumentParser):
    """Add the default arguments username, password, region to the parser."""
    parser.add_argument('username', help='PodMe.com username')
    parser.add_argument('password', help='PodMe.com password')


def main():
    """Main function."""
    parser = main_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
