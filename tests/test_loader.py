"""
Very basic tests
"""

import os
import pathlib

import pytest

from dynaconf import Dynaconf


def test_basic_environment_based_settings(
    basic_environment_parameters,
    default_settings: pathlib.Path,
):
    """
    Test simple loading of configuration from AWS SSM on a per-environment
    basis.

    """

    dev_settings = Dynaconf(
        environments=True,
        FORCE_ENV_FOR_DYNACONF="development",
        settings_file=str(default_settings.resolve()),
        LOADERS_FOR_DYNACONF=[
            "dynaconf_aws_loader.loader",
        ],
    )

    assert dev_settings.current_env == "development"
    assert dev_settings.AWS_SSM_PARAMETER_PROJECT_PREFIX == "testapp"

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
        settings_file=str(default_settings.resolve()),
        LOADERS_FOR_DYNACONF=[
            "dynaconf_aws_loader.loader",
        ],
    )

    assert prod_settings.current_env == "production"
    assert prod_settings.AWS_SSM_PARAMETER_PROJECT_PREFIX == "testapp"

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
    environment_less_parameters,
    settings_without_sections: pathlib.Path,
):
    """
    Test simple loading of configuration from AWS SSM with no environment-based layers.
    """

    settings = Dynaconf(
        environments=False,
        settings_file=str(settings_without_sections.resolve()),
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
    environment_less_parameters,
):
    """
    Load the AWS SSM project prefix identifier from os.environ, to avoid the
    chicken/egg problem if you want to only use env vars instead of having a
    settings.toml|yaml|etc file present.
    """

    os.environ["AWS_SSM_PARAMETER_PROJECT_PREFIX"] = "testapp"

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

    # From Parameter store
    assert settings.PRODUCTS == {"plans": ["monthly", "yearly"]}
    assert settings["DATABASE"] == {"host": "db.example.com", "password": "password"}

    del os.environ["AWS_SSM_PARAMETER_PROJECT_PREFIX"]


def test_with_namespace(
    environment_with_namespaced_parameters,
    default_settings_with_namespace: pathlib.Path,
):
    """'An optional namespace may be provided to further group/segment hierarchical parameters."""

    dev_settings = Dynaconf(
        environments=True,
        FORCE_ENV_FOR_DYNACONF="development",
        settings_file=str(default_settings_with_namespace.resolve()),
        LOADERS_FOR_DYNACONF=[
            "dynaconf_aws_loader.loader",
        ],
    )

    assert dev_settings.current_env == "development"
    assert dev_settings.AWS_SSM_PARAMETER_PROJECT_PREFIX == "bigapp"
    assert dev_settings.AWS_SSM_PARAMETER_NAMESPACE == "consumer"

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
