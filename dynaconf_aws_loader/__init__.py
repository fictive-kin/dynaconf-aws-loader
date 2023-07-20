"""
Dynaconf Loader for AWS Secrets Manager
"""
import typing as t

from importlib.metadata import version

# Pull version from the package data; canonical source is pyproject.toml
__version__ = version(__package__)


def generate_loader_identifier(path: str, env: str):
    """
    The loader identifier, which is used to identify the provenance of compiled
    configuration key/value pairs in the resulting ``Settings`` object.

    :param path: String-based path to identify where the value has been sourced from
    :param env: String-based env name
    """

    # Dynamic import here, due to the changes between Dynaconf 3.1 and 3.2 with
    # respect to loader identifiers.
    try:
        # Use the new-style source metadata loading for better introspection
        # of where values are sourced from.
        from dynaconf.loaders.base import SourceMetadata

        loader_identifier = SourceMetadata(loader="aws-ssm", identifier=path, env=env)
    except ImportError:  # Dynaconf<=3.1, simply return a string.
        # Use the old-style string identifiers.
        loader_identifier = "aws-ssm"

    return loader_identifier
