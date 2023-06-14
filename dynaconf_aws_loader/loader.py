"""
Custom Dynaconf loader for Amazon System Parameter Store (SSM)

"""
from __future__ import annotations
import typing as t

import os
import logging
import boto3
from botocore.exceptions import ClientError, BotoCoreError, NoRegionError

from dynaconf.utils import build_env_list
from dynaconf.utils.parse_conf import parse_conf_data

from . import IDENTIFIER
from .util import slashes_to_dict

if t.TYPE_CHECKING:
    from mypy_boto3_ssm.client import SSMClient


logger = logging.getLogger("dynaconf")


def get_client(obj) -> SSMClient:
    """Get a boto3 client to access AWS System Parameter Store"""

    endpoint_url = obj.get("AWS_ENDPOINT_URL_FOR_DYNACONF")
    session = boto3.session.Session(**obj.get("AWS_SESSION_FOR_DYNACONF", {}))
    client = session.client(service_name="ssm", endpoint_url=endpoint_url)
    return client


def load(
    obj,
    env: str | None = None,
    silent: bool = True,
    key: str | None = None,
    validate: bool = False,
):
    """
    Reads and loads in to ``obj`` a single key or all keys from the Parameter
    Store source.

    The structure that this loader expects from the path-based organization in
    SSM is:

    /<project>/<environment>/<param>

    An optional ``namespace`` can be specified, e.g. for PR review app
    configurations:

    /<project>/<namespace>/<environment>/<param>

    Note that if you choose to use a ``namespace`` identifier, it must not
    conflict with existing or future ``project`` and ``environment``
    identifiers.

    AWS SSM has the following key (and thus path) limitations:

    - Parameter names are case sensitive.
    - A parameter name must be unique within an Amazon Web Services Region
    - A parameter name can’t be prefixed with “ aws” or “ ssm” (case-insensitive)
    - Parameter names can include only the following symbols and letters: a-zA-Z0-9_.-
      In addition, the slash character ( / ) is used to delineate hierarchies in parameter names.
    - A parameter name can’t include spaces.
    - Parameter hierarchies are limited to a maximum depth of fifteen levels

    For this loader to function correctly and securely, you should be using IAM
    policies to restrict which parameters can be read/mutated. Policies can be
    enaced on a glob-path basis, which will ensure that the only parameters that
    can be fetched/hydrated into the local object instance are the ones that the
    current environment is permitted to load.

    :param obj: the settings instance
    :param env: settings current env (upper case) default='DEVELOPMENT'
    :param silent: if errors should raise an exception
    :param key: if defined load a single key, else load all from ``env``
    :param validate: will the loaded data be validated when setting on ``obj``
    :return: None

    """

    try:
        client = get_client(obj)
    except NoRegionError as exc:
        logging.exception(exc)
        # We have no region, therefore, we cannot load anything. Just return
        return

    env_list = build_env_list(obj, env or obj.current_env)

    project_prefix: str = obj.get(
        "AWS_SSM_PARAMETER_PROJECT_PREFIX",
        os.environ.get("AWS_SSM_PARAMETER_PROJECT_PREFIX"),
    )

    if project_prefix is None:
        raise ValueError(
            "AWS_SSM_PARAMETER_PROJECT_PREFIX must be set in settings"
            " or environment for AWS SSM loader to work."
        )
    namespace_prefix: str | None = obj.get("AWS_SSM_PARAMETER_NAMESPACE", None)

    for env_name in env_list:
        env_name = env_name.lower()
        path = f"/{project_prefix}/{env_name}"

        if namespace_prefix is not None:
            path = f"{path}/{namespace_prefix}"

        try:
            if key:
                logger.debug(
                    "Attempting to load parameter %s from AWS SSM for env %s."
                    % (key, env_name)
                )

                value = client.get_parameter(Name=f"/{path}/{key}", WithDecryption=True)
                if data := value.get("Parameter"):
                    parsed_value = parse_conf_data(
                        data["Value"], tomlfy=True, box_settings=obj
                    )
                    if parsed_value:
                        obj.set(key, parsed_value, validate=validate)

            else:
                # With no ``key`` specified, we load all data from the source
                # that we are allowed to access.
                logger.debug(
                    "Attempting to load all parameters from AWS SSM for path %s." % path
                )
                data = []
                paginator = client.get_paginator("get_parameters_by_path")
                for page in paginator.paginate(
                    Path=path, Recursive=True, WithDecryption=True
                ):
                    for parameter in page["Parameters"]:
                        data.append({parameter["Name"]: parameter["Value"]})

                result = parse_conf_data(data=slashes_to_dict(data), tomlfy=True)

                if result and project_prefix in result:
                    # Prune out the prefixes before setting on the object
                    result = result[project_prefix]

                    if result and env_name in result:
                        result = result[env_name]

                    if namespace_prefix is not None and namespace_prefix in result:
                        result = result[namespace_prefix]

                    obj.update(
                        result,
                        loader_identifier=IDENTIFIER,
                        validate=validate,
                    )
        except (ClientError, BotoCoreError):
            logger.error("Could not connect to AWS SSM.")
            if silent is False:
                raise
        except Exception:
            if silent:
                return False
            raise
