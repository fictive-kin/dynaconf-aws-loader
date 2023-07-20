"""
Tests for the loader, sans Dynaconf wrapper
"""

from datetime import datetime
import logging
from dynaconf.base import Settings
import pytest

from botocore.stub import Stubber

from dynaconf_aws_loader.loader import (
    get_client,
    build_env_list,
    _fetch_single_parameter,
    _fetch_all_parameters,
    load,
)


@pytest.fixture
def stubbed_client(mocker):
    """
    Use ``boto3`` stubbed client for testing purposes.

    The stub must be activated before usage.
    """

    settings = mocker.MagicMock()
    data = {"SSM_ENDPOINT_URL_FOR_DYNACONF": None, "SSM_SESSION_FOR_DYNACONF": {}}
    settings.get.side_effect = data.get
    client = get_client(settings)

    return Stubber(client)


def test_get_client_default(mocker):
    """Return a constructed ``boto3`` client for SSM."""

    settings = mocker.MagicMock()
    data = {"SSM_ENDPOINT_URL_FOR_DYNACONF": None, "SSM_SESSION_FOR_DYNACONF": {}}
    settings.get.side_effect = data.get

    client = get_client(obj=settings)

    # Defaults
    assert client.meta.endpoint_url == "http://localhost:4566"


def test_get_client_custom_endpoint(mocker):
    """
    Get a ``boto3`` client for SSM but with a custom endpoint
    """
    settings = mocker.MagicMock()
    data = {
        "SSM_ENDPOINT_URL_FOR_DYNACONF": "http://example.com:5555",
        "SSM_SESSION_FOR_DYNACONF": {},
    }
    settings.get.side_effect = data.get

    client = get_client(obj=settings)
    assert client.meta.endpoint_url == "http://example.com:5555"
    assert client.meta.region_name == "us-east-1"


def test_get_client_custom_boto3_session_parameters(mocker):
    """
    Get a ``boto3`` client for SSM but with custom parameters for Session
    """
    settings = mocker.MagicMock()
    data = {
        "SSM_SESSION_FOR_DYNACONF": {
            "region_name": "us-west-1",
        },
    }
    settings.get.side_effect = data.get

    client = get_client(obj=settings)
    assert client.meta.region_name == "us-west-1"


def test_build_basic_env_list_without_default(mocker):
    """Build list of environments for loader to use as path segments"""

    settings = mocker.MagicMock()
    data = {
        "SSM_LOAD_DEFAULT_ENV_FOR_DYNACONF": False,
    }
    settings.get.side_effect = data.get
    result = build_env_list(settings, env="testing")

    assert list(result) == ["testing"]


@pytest.mark.parametrize("env_name", ["default", "staging"])
def test_build_basic_env_list_from_settings_with_default(mocker, env_name):
    """Build list of environments for loader based on environments with default"""

    settings = mocker.MagicMock()
    data = {
        "SSM_LOAD_DEFAULT_ENV_FOR_DYNACONF": True,
        "DEFAULT_ENV_FOR_DYNACONF": env_name,
    }
    settings.get.side_effect = data.get

    result = build_env_list(settings, env="testing")
    assert list(result) == [env_name, "testing"]


def test_build_basic_env_list_from_settings_do_not_load_default(mocker):
    """Build environment list, but ignore default even if set."""

    settings = mocker.MagicMock()
    data = {
        "SSM_LOAD_DEFAULT_ENV_FOR_DYNACONF": False,
        "DEFAULT_ENV_FOR_DYNACONF": "do-not-load-me",
    }
    settings.get.side_effect = data.get

    result = build_env_list(settings, env="testing")
    assert list(result) == ["testing"]


def test_fetch_single_parameter_missing(stubbed_client, caplog):
    """
    Fetch a single parameter from SSM, but it doesn't exist.

    Ensure that our logger captures this information.
    """

    stubbed_client.add_client_error(
        "get_parameter", service_error_code="ParameterNotFound"
    )

    with stubbed_client:
        with pytest.raises(stubbed_client.client.exceptions.ParameterNotFound):
            with caplog.at_level(logging.INFO, logger="dynaconf.aws_loader"):
                _fetch_single_parameter(
                    stubbed_client.client,
                    project_prefix="foobar",
                    env_name="testing",
                    key="baldur",
                    silent=False,
                )

    assert caplog.record_tuples == [
        (
            "dynaconf.aws_loader",
            logging.INFO,
            "Parameter with path /foobar/testing/baldur does not exist in AWS SSM.",
        )
    ]


def test_fetch_all_parameters_missing(stubbed_client, caplog):
    """
    Fetch all parameters nested under a path hierarchy, but said hierarchy
    does not exist.

    Ensure that our logger captures this information.
    """

    stubbed_client.add_client_error(
        "get_parameters_by_path", service_error_code="ParameterNotFound"
    )

    with stubbed_client:
        with pytest.raises(stubbed_client.client.exceptions.ParameterNotFound):
            with caplog.at_level(logging.INFO, logger="dynaconf.aws_loader"):
                _fetch_all_parameters(
                    stubbed_client.client,
                    project_prefix="foobar",
                    env_name="testing",
                    silent=False,
                )

    assert caplog.record_tuples == [
        (
            "dynaconf.aws_loader",
            logging.INFO,
            "Parameter with path /foobar/testing does not exist in AWS SSM.",
        )
    ]


def test_fetch_single_parameter(stubbed_client):
    """Fetch a single parameter from SSM."""

    stubbed_response = {
        "Parameter": {
            "Name": "/foobar/testing/baldur",
            "Type": "String",
            "Value": "gate",
            "Version": 1,
            "LastModifiedDate": datetime(2015, 1, 1),
            "ARN": "fake::arn",
            "DataType": "text",
        }
    }
    expected_params = {"Name": "/foobar/testing/baldur", "WithDecryption": True}

    stubbed_client.add_response("get_parameter", stubbed_response, expected_params)

    with stubbed_client:
        result = _fetch_single_parameter(
            stubbed_client.client,
            project_prefix="foobar",
            env_name="testing",
            key="baldur",
        )

    assert result == "gate"


def test_fetch_all_parameters_by_path(stubbed_client):
    """Fetch all parameters by hierarchical path from SSM."""

    stubbed_response = {
        "Parameters": [
            {
                "Name": "/foobar/testing/database/host",
                "Type": "String",
                "Value": "localhost",
                "Version": 1,
                "LastModifiedDate": datetime(2015, 1, 1),
                "ARN": "fake::arn",
                "DataType": "text",
            },
            {
                "Name": "/foobar/testing/database/port",
                "Type": "String",
                "Value": "5432",
                "Version": 1,
                "LastModifiedDate": datetime(2015, 1, 1),
                "ARN": "fake::arn",
                "DataType": "text",
            },
            {
                "Name": "/foobar/testing/debug",
                "Type": "String",
                "Value": "@bool True",
                "Version": 1,
                "LastModifiedDate": datetime(2015, 1, 1),
                "ARN": "fake::arn",
                "DataType": "text",
            },
        ],
    }

    expected_params = {
        "Path": "/foobar/testing",
        "Recursive": True,
        "WithDecryption": True,
    }

    stubbed_client.add_response(
        "get_parameters_by_path", stubbed_response, expected_params
    )

    with stubbed_client:
        result = _fetch_all_parameters(
            stubbed_client.client,
            project_prefix="foobar",
            env_name="testing",
        )

    assert result == {"database": {"host": "localhost", "port": 5432}, "debug": True}


def test_load(mocker, stubbed_client):
    """Straightforward test of main functionality of AWS SSM loader"""

    settings = Settings(
        SSM_LOAD_DEFAULT_ENV_FOR_DYNACONF=False,
        SSM_PARAMETER_PROJECT_PREFIX_FOR_DYNACONF="foobar",
    )

    stubbed_response = {
        "Parameters": [
            {
                "Name": "/foobar/testing/database/host",
                "Type": "String",
                "Value": "localhost",
                "Version": 1,
                "LastModifiedDate": datetime(2015, 1, 1),
                "ARN": "fake::arn",
                "DataType": "text",
            },
            {
                "Name": "/foobar/testing/database/port",
                "Type": "String",
                "Value": "5432",
                "Version": 1,
                "LastModifiedDate": datetime(2015, 1, 1),
                "ARN": "fake::arn",
                "DataType": "text",
            },
            {
                "Name": "/foobar/testing/debug",
                "Type": "String",
                "Value": "@bool True",
                "Version": 1,
                "LastModifiedDate": datetime(2015, 1, 1),
                "ARN": "fake::arn",
                "DataType": "text",
            },
        ],
    }

    expected_params = {
        "Path": "/foobar/testing",
        "Recursive": True,
        "WithDecryption": True,
    }

    stubbed_client.add_response(
        "get_parameters_by_path", stubbed_response, expected_params
    )

    mocker.patch(
        "dynaconf_aws_loader.loader.get_client", return_value=stubbed_client.client
    )

    with stubbed_client:
        load(settings, env="testing")

    assert settings.DATABASE.HOST == "localhost"
    assert settings.DATABASE.PORT == 5432
    assert settings.DEBUG == True
