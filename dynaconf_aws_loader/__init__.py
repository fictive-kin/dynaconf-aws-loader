"""
Dynaconf Loader for AWS Secrets Manager
"""

from importlib.metadata import version

# Pull version from the package data; canonical source is pyproject.toml
__version__ = version(__package__)

# The loader identifier, which is used to identify the provenance of compiled
# configuration key/value pairs in the resulting ``Settings`` object.
IDENTIFIER = "aws-ssm"
