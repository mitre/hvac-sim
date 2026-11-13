"""
Deprecated flag names, still accepted by the PLC and the HMI.
"""

import argparse
import logging

logger = logging.getLogger(__name__)


class _DeprecatedAlias(argparse.Action):
    def __init__(self, option_strings, dest, new, **kwargs):
        super().__init__(option_strings, dest, **kwargs)
        self.new = new

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
        used = dict(getattr(namespace, "deprecated_flags", {}))
        used[option_string] = self.new
        namespace.deprecated_flags = used


def add_deprecated_alias(parser, old, new):
    """Accept old as a hidden alias of the flag new."""
    dest = new.lstrip("-").replace("-", "_")
    parser.add_argument(old, dest=dest, action=_DeprecatedAlias, new=new, default=argparse.SUPPRESS, help=argparse.SUPPRESS)


def warn_deprecated(args):
    """Log one warning for each deprecated flag on the command line."""
    for old, new in getattr(args, "deprecated_flags", {}).items():
        logger.warning("%s is deprecated, use %s", old, new)
