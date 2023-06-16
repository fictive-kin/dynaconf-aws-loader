"""
Very basic tests
"""

import os
import pathlib

import pytest

from dynaconf import Dynaconf

from dynaconf_aws_loader.util import NamespaceFilter


def test_basic_environment_based_settings(
    basic_settings: pathlib.Path,
):
    """
    Test simple loading of configuration from AWS SSM on a per-environment
    basis.

    """

    dev_settings = Dynaconf(
        environments=True,
        FORCE_ENV_FOR_DYNACONF="development",
        settings_file=str(basic_settings.resolve()),
        LOADERS_FOR_DYNACONF=[
            "dynaconf_aws_loader.loader",
        ],
    )

    assert dev_settings.current_env == "development"
    assert dev_settings.SSM_PARAMETER_PROJECT_PREFIX_FOR_DYNACONF == "basic"

    assert dev_settings.MY_CONFIG_VALUE == "test123"

    # Loaded from default env
    assert dev_settings.PRODUCTS == {"plans": ["monthly", "yearly"]}

    # Ensure environment separation of data
    with pytest.raises(AttributeError):
        dev_settings.DATABASE

    with pytest.raises(KeyError):
        dev_settings["DATABASE"]

    prod_settings = Dynaconf(
        environments=True,
        FORCE_ENV_FOR_DYNACONF="production",
        settings_file=str(basic_settings.resolve()),
        LOADERS_FOR_DYNACONF=[
            "dynaconf_aws_loader.loader",
        ],
    )

    assert prod_settings.current_env == "production"
    assert prod_settings.SSM_PARAMETER_PROJECT_PREFIX_FOR_DYNACONF == "basic"

    # Loaded from default env
    assert prod_settings.PRODUCTS == {"plans": ["monthly", "yearly"]}

    assert prod_settings["DATABASE"]["HOST"] == "db.example.com"

    # Ensure decryption
    assert prod_settings["DATABASE"]["PASSWORD"] == "password"

    # Can't load [development] environment config values when current
    # environment is [production]
    with pytest.raises(AttributeError):
        assert prod_settings.MY_CONFIG_VALUE == "test123"

    # Cross-load from a different environment explicitly
    with prod_settings.using_env("development"):
        assert prod_settings.MY_CONFIG_VALUE == "test123"


def test_settings_with_no_environments(
    settings_without_environments: pathlib.Path,
):
    """
    Test simple loading of configuration from AWS SSM with no environment-based layers.
    """

    settings = Dynaconf(
        environments=False,
        settings_file=str(settings_without_environments.resolve()),
        LOADERS_FOR_DYNACONF=[
            "dynaconf_aws_loader.loader",
        ],
    )

    # From the ``settings.toml`` that is specified via ``settings_without_sections`` fixture
    assert settings.PRODUCT_NAME == "foobar"

    # From Parameter store
    assert settings.PRODUCTS == {"plans": ["monthly", "yearly"]}
    assert settings["DATABASE"] == {"host": "db.example.com", "password": "password"}


def test_settings_get_project_prefix_from_environ(
    settings_without_environments: pathlib.Path,
):
    """
    Load the AWS SSM project prefix identifier from os.environ, to avoid the
    chicken/egg problem if you want to only use env vars instead of having a
    settings.toml|yaml|etc file present.
    """

    os.environ["SSM_PARAMETER_PROJECT_PREFIX_FOR_DYNACONF"] = "basic-envless"

    # Example var for built-in dynaconf env loader to pick up
    os.environ["DYNACONF_PRODUCT_NAME"] = "foobar"

    settings = Dynaconf(
        environments=False,
        LOADERS_FOR_DYNACONF=[
            "dynaconf_aws_loader.loader",
            "dynaconf.loaders.env_loader",
        ],
    )

    # From the ENV vars that we load
    assert settings.PRODUCT_NAME == "foobar"
    assert settings.SSM_PARAMETER_PROJECT_PREFIX_FOR_DYNACONF == "basic-envless"

    # From Parameter store
    assert settings.PRODUCTS == {"plans": ["monthly", "yearly"]}
    assert settings["DATABASE"] == {"host": "db.example.com", "password": "password"}

    del os.environ["SSM_PARAMETER_PROJECT_PREFIX_FOR_DYNACONF"]
    del os.environ["DYNACONF_PRODUCT_NAME"]


def test_with_namespace(settings_with_namespace: pathlib.Path):
    """
    An optional namespace may be provided to further group/segment hierarchical
    parameters.
    """

    namespace = "consumer"
    project_name = "basic-namespaced"

    dev_settings = Dynaconf(
        environments=True,
        FORCE_ENV_FOR_DYNACONF="development",
        settings_file=str(settings_with_namespace.resolve()),
        LOADERS_FOR_DYNACONF=[
            "dynaconf_aws_loader.loader",
        ],
    )

    assert dev_settings.current_env == "development"
    assert dev_settings.SSM_PARAMETER_PROJECT_PREFIX_FOR_DYNACONF == project_name
    assert dev_settings.SSM_PARAMETER_NAMESPACE_FOR_DYNACONF == namespace

    # From settings.toml [default] config
    assert dev_settings.PRODUCT_NAME == "foobar"

    # Ensure our config values are present, and access is transparent to the provided namespace
    assert dev_settings.PRODUCTS == {"plans": ["monthly", "yearly"]}
    assert dev_settings.MY_CONFIG_VALUE == "test123"

    # Ensure environment separation of data
    with pytest.raises(AttributeError):
        dev_settings.DATABASE

    with pytest.raises(KeyError):
        dev_settings["DATABASE"]


def test_with_namespace_merging(
    settings_with_namespace_and_non_namespaced: pathlib.Path,
):
    """
    A namespace was provided, and we desire merging those with the
    non-namespaced path.

    e.g.

    /testapp/qa/* keys will be loaded, and /testapp/qa/pr-123/* keys will be loaded and
    override those that were present in /testapp/qa/*

    """

    project_name = "combo"
    namespace = "pr-123"

    settings = Dynaconf(
        environments=True,
        FORCE_ENV_FOR_DYNACONF="production",
        settings_file=str(settings_with_namespace_and_non_namespaced.resolve()),
        LOADERS_FOR_DYNACONF=[
            "dynaconf_aws_loader.loader",
        ],
    )

    assert settings.current_env == "production"
    assert settings.SSM_PARAMETER_PROJECT_PREFIX_FOR_DYNACONF == project_name
    assert settings.SSM_PARAMETER_NAMESPACE_FOR_DYNACONF == namespace

    # Non-namespaced parameter/values:
    # /combo/production/database/password => production-password
    # /combo/production/database/host => production.example.com
    # /combo/production/region => region-identifier
    #
    # Namespaced ones:
    # /combo/production/pr-123/database/password => namespaced-production-password
    # /combo/production/pr-123/database/host => namespaced.production.example.com
    #
    # The namespaced values should override the regular non-namespaced ones, and
    # merge the rest.

    assert settings["DATABASE"] == {
        "host": "namespaced.production.example.com",
        "password": "namespaced-production-password",
    }

    # Applied as default for all envs/namespaces
    assert settings.PRODUCTS == {"plans": ["monthly", "yearly"]}

    # applied for non-namespaced production env
    assert settings.REGION == "region-identifier"

    # The namespaced data will still be available directly on the configuration
    # object. To strip this from the final settings object, we'll need a filter.
    assert settings.get("pr-123") is not None


def test_with_namespace_merging_and_filter(
    settings_with_namespace_and_non_namespaced: pathlib.Path,
):
    """
    A namespace was provided, and we desire merging those with the
    non-namespaced path, but we want to filter out the namespaced block
    in the final settings.

    """

    project_name = "combo"
    namespace = "pr-123"
    namespace_filter_pattern = "pr-"

    settings = Dynaconf(
        environments=True,
        FORCE_ENV_FOR_DYNACONF="production",
        settings_file=str(settings_with_namespace_and_non_namespaced.resolve()),
        LOADERS_FOR_DYNACONF=[
            "dynaconf_aws_loader.loader",
        ],
        aws_ssm_namespace_filter_strategy=NamespaceFilter(namespace_filter_pattern),
    )

    assert settings.current_env == "production"
    assert settings.SSM_PARAMETER_PROJECT_PREFIX_FOR_DYNACONF == project_name
    assert settings.SSM_PARAMETER_NAMESPACE_FOR_DYNACONF == namespace

    assert settings["DATABASE"] == {
        "host": "namespaced.production.example.com",
        "password": "namespaced-production-password",
    }

    # Applied as default for all envs/namespaces
    assert settings.PRODUCTS == {"plans": ["monthly", "yearly"]}
    assert settings.REGION == "region-identifier"

    assert settings.get("pr-123") is None
