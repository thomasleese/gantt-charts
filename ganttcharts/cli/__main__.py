"""CLI runner."""

from argparse import ArgumentParser

from .. import __description__

from . import send_summary_emails


def main():
    """Run the command-line tool."""

    parser = ArgumentParser(description=__description__)

    subparsers = parser.add_subparsers(title='commands')
    send_summary_emails.add_subparser(subparsers)
    args = parser.parse_args()

    try:
        func = args.func
    except AttributeError:
        parser.print_help()
    else:
        func(args)


if __name__ == '__main__':
    main()
