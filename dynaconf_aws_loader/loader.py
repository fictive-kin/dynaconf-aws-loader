"""
Custom Dynaconf loader for Amazon System Parameter Store (SSM)

"""
from __future__ import annotations
import typing as t

import os
import logging
import boto3
from botocore.exceptions import ClientError, BotoCoreError, NoRegionError

from dynaconf.utils.parse_conf import parse_conf_data

from .util import slashes_to_dict, pull_from_env_or_obj
from . import generate_loader_identifier

if t.TYPE_CHECKING:
    from mypy_boto3_ssm.client import SSMClient
    from dynaconf.base import Settings


logger = logging.getLogger("dynaconf.aws_loader")


def get_client(obj) -> SSMClient:
    """Get a boto3 client to access AWS System Parameter Store"""

    endpoint_url = obj.get("SSM_ENDPOINT_URL_FOR_DYNACONF")
    session = boto3.session.Session(**obj.get("SSM_SESSION_FOR_DYNACONF", {}))
    client = session.client(service_name="ssm", endpoint_url=endpoint_url)
    return client


def build_env_list(obj: Settings, env: t.Optional[str]) -> t.Iterable[str]:
    """
    Build env list for loader to iterate.

    Ensure we are building the env list in such a way that we are not going to
    be hitting the remote AWS SSM Parameter Store endpoints needlessly. Let's only
    hit `DEFAULT_ENV_FOR_DYNACONF`, the currently set environment on the settings object,
    and the manually set `env` (if any).

    Some of this logic is similar to `dynaconf.utils.build_env_list`.
    """

    env_list = []
    if obj.get("SSM_LOAD_DEFAULT_ENV_FOR_DYNACONF", True) is True:
        default_env_name: str = obj.get("DEFAULT_ENV_FOR_DYNACONF", "default")
        if default_env_name and (default_env_name := default_env_name.lower()):
            env_list.append(default_env_name)

    # add a manually set env, if specified
    if env and (env_identifier := env.lower()) not in env_list:
        env_list.append(env_identifier)

    # Ensure any leading/trailing whitespace is removed
    return map(str.strip, env_list)


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

    prefix_key_name = "SSM_PARAMETER_PROJECT_PREFIX_FOR_DYNACONF"
    namespace_key_name = "SSM_PARAMETER_NAMESPACE_FOR_DYNACONF"

    try:
        client = get_client(obj)
    except NoRegionError:
        if silent:
            # We have no region, therefore, we cannot load anything.
            logging.exception(
                "An AWS region must be available/specified for the Dynaconf"
                " AWS Loader to function."
            )
            return
        raise

    project_prefix = pull_from_env_or_obj(prefix_key_name, os.environ, obj)
    namespace_prefix = pull_from_env_or_obj(namespace_key_name, os.environ, obj)

    if project_prefix is None:
        raise ValueError(
            f"{prefix_key_name} must be set in settings"
            " or environment for AWS SSM loader to work."
        )

    env_list = build_env_list(obj, env or obj.current_env)

    for env_name in env_list:
        env_name = env_name.lower()
        path = f"/{project_prefix}/{env_name}"

        if namespace_prefix is not None:
            path = f"{path}/{namespace_prefix}"

        loader_identifier = generate_loader_identifier(path, env)

        if key is not None:
            value = _fetch_single_parameter(
                client,
                project_prefix=project_prefix,
                env_name=env_name,
                namespace_prefix=namespace_prefix,
                key=key,
                silent=silent,
            )
            if value:
                obj.set(key, value, validate=validate)

            return
        else:
            # Fetch non-namespaced and namespaced keys, merging the latter into
            # the former.
            # TODO use single path query for both
            normal_results = _fetch_all_parameters(
                client=client,
                project_prefix=project_prefix,
                env_name=env_name,
                namespace_prefix=None,
                silent=silent,
            )

            if normal_results:
                filter_strategy = obj.get("AWS_SSM_NAMESPACE_FILTER_STRATEGY")
                if filter_strategy:
                    normal_results = filter_strategy(normal_results)

                obj.update(
                    normal_results,
                    loader_identifier=loader_identifier,
                    validate=validate,
                )

            if namespace_prefix is not None:
                namespaced_results = _fetch_all_parameters(
                    client=client,
                    project_prefix=project_prefix,
                    env_name=env_name,
                    namespace_prefix=namespace_prefix,
                    silent=silent,
                )

                if namespaced_results:
                    obj.update(
                        namespaced_results,
                        loader_identifier=loader_identifier,
                        validate=validate,
                    )


def _fetch_single_parameter(
    client,
    project_prefix: str,
    env_name: str,
    key: str,
    namespace_prefix: str | None = None,
    silent: bool = True,
):
    """
    Fetch single parameter by path.
    """

    path = f"/{project_prefix}/{env_name}"
    if namespace_prefix is not None:
        path = f"{path}/{namespace_prefix}"

    path = f"{path}/{key}"

    logger.debug("Attempting to load a single parameter %s from AWS SSM" % path)

    try:
        value = client.get_parameter(Name=path, WithDecryption=True)
    except ClientError as exc:
        if silent:
            return
        if exc.response.get("Error", {}).get("Code") == "ParameterNotFound":
            logger.info("Parameter with path %s does not exist in AWS SSM." % path)
        raise
    except BotoCoreError:
        if silent:
            return
        logger.error(
            "Could not connect to AWS SSM at endpoint %s." % client.meta.endpoint_url
        )
        raise

    if data := value.get("Parameter"):
        value = parse_conf_data(data["Value"], tomlfy=True)

    return value


def _fetch_all_parameters(
    client,
    project_prefix: str,
    env_name: str,
    namespace_prefix: str | None = None,
    silent: bool = True,
):
    """
    Fetch all keys by path segment.
    """

    path = f"/{project_prefix}/{env_name}"
    if namespace_prefix is not None:
        path = f"{path}/{namespace_prefix}"

    logger.debug("Attempting to load all parameters from AWS SSM for path %s" % path)

    data = []
    paginator = client.get_paginator("get_parameters_by_path")

    try:
        for page in paginator.paginate(Path=path, Recursive=True, WithDecryption=True):
            for parameter in page["Parameters"]:
                data.append({parameter["Name"]: parameter["Value"]})

    except ClientError as exc:
        if silent:
            return
        if exc.response.get("Error", {}).get("Code") == "ParameterNotFound":
            logger.info("Parameter with path %s does not exist in AWS SSM." % path)
        raise
    except BotoCoreError:
        if silent:
            return
        logger.error(
            "Could not connect to AWS SSM at endpoint %s." % client.meta.endpoint_url
        )
        raise

    result = parse_conf_data(data=slashes_to_dict(data), tomlfy=True)

    if result and project_prefix in result:
        # Prune out the prefixes before setting on the object
        result = result[project_prefix]

        if result and env_name in result:
            result = result[env_name]

        if namespace_prefix is not None and namespace_prefix in result:
            result = result[namespace_prefix]

    return result
