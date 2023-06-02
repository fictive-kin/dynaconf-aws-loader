"""
Basic test fixtures

"""

import json
from pathlib import Path
import pytest

import boto3
from localstack_client.patch import enable_local_endpoints
from mypy_boto3_ssm.client import SSMClient


@pytest.fixture(autouse=True)
def patch_boto3_for_localstack():
    """
    Mock out any boto3 connections to use localstack
    """
    yield enable_local_endpoints()


@pytest.fixture(scope="session")
def docker_localstack(docker_services):
    """Start the localstack service for the integration tests"""

    docker_services.start("localstack")
    public_port = docker_services.wait_for_service("localstack", 4566)
    return f"{docker_services.docker_ip}:{public_port}"


@pytest.fixture
def ssm_client(docker_localstack):
    """An IAM client to use for the test suite."""

    return boto3.client("ssm")


@pytest.fixture
def default_settings(tmp_path) -> Path:
    """A fixtured temporary file with a [default] settings section, only."""

    data = """
    [default]
    AWS_SSM_PARAMETER_PROJECT_PREFIX = 'testapp'
    PRODUCT_NAME = "foobar"
    """

    settings_file = tmp_path / "settings.toml"
    settings_file.write_text(data)
    return settings_file


@pytest.fixture
def default_settings_with_namespace(tmp_path) -> Path:
    """
    A fixtured temporary file with a [default] settings section, and an explict
    namespace.
    """

    data = """
    [default]
    AWS_SSM_PARAMETER_PROJECT_PREFIX = 'bigapp'
    AWS_SSM_PARAMETER_NAMESPACE = 'consumer'
    PRODUCT_NAME = "foobar"
    """

    settings_file = tmp_path / "settings.toml"
    settings_file.write_text(data)
    return settings_file


@pytest.fixture
def settings_without_sections(tmp_path) -> Path:
    """A fixtured temporary file with no environment/default sections."""

    data = """
    AWS_SSM_PARAMETER_PROJECT_PREFIX = 'testapp'
    PRODUCT_NAME = "foobar"
    """

    settings_file = tmp_path / "settings.toml"
    settings_file.write_text(data)
    return settings_file


@pytest.fixture
def basic_environment_parameters(ssm_client: SSMClient):
    """Setup AWS SSM with some basic path-based parameter data, and remove once completed."""

    ssm_client.put_parameter(
        Name="/testapp/default/products",
        # Use @json cast for Dynaconf
        # https://www.dynaconf.com/configuration/#auto_cast
        Value="@json %s" % json.dumps({"plans": ["monthly", "yearly"]}),
        Type="String",
    )
    ssm_client.put_parameter(
        Name="/testapp/development/my_config_value", Value="test123", Type="String"
    )
    ssm_client.put_parameter(
        Name="/testapp/production/database/password",
        Value="password",
        Type="SecureString",
    )
    ssm_client.put_parameter(
        Name="/testapp/production/database/host",
        Value="db.example.com",
        Type="String",
    )

    yield

    ssm_client.delete_parameters(
        Names=[
            "/testapp/production/database/host",
            "/testapp/production/database/password",
            "/testapp/development/my_config_value",
            "/testapp/default/products",
        ]
    )


@pytest.fixture
def environment_less_parameters(ssm_client: SSMClient):
    """Path-based parameters, but without environment layering."""

    ssm_client.put_parameter(
        Name="/testapp/default/products",
        # Use @json cast for Dynaconf
        # https://www.dynaconf.com/configuration/#auto_cast
        Value="@json %s" % json.dumps({"plans": ["monthly", "yearly"]}),
        Type="String",
    )
    ssm_client.put_parameter(
        Name="/testapp/default/my_config_value", Value="test123", Type="String"
    )
    ssm_client.put_parameter(
        Name="/testapp/default/database/password",
        Value="password",
        Type="SecureString",
    )
    ssm_client.put_parameter(
        Name="/testapp/default/database/host",
        Value="db.example.com",
        Type="String",
    )

    yield

    ssm_client.delete_parameters(
        Names=[
            "/testapp/default/database/host",
            "/testapp/default/database/password",
            "/testapp/default/my_config_value",
            "/testapp/default/products",
        ]
    )


@pytest.fixture
def environment_with_namespaced_parameters(ssm_client: SSMClient):
    """Setup AWS SSM with environment and namespace based parameters."""

    namespace = "consumer"

    ssm_client.put_parameter(
        Name=f"/bigapp/development/{namespace}/products",
        # Use @json cast for Dynaconf
        # https://www.dynaconf.com/configuration/#auto_cast
        Value="@json %s" % json.dumps({"plans": ["monthly", "yearly"]}),
        Type="String",
    )
    ssm_client.put_parameter(
        Name=f"/bigapp/development/{namespace}/my_config_value",
        Value="test123",
        Type="String",
    )
    ssm_client.put_parameter(
        Name=f"/bigapp/production/{namespace}/database/password",
        Value="password",
        Type="SecureString",
    )
    ssm_client.put_parameter(
        Name=f"/bigapp/production/{namespace}/database/host",
        Value="db.example.com",
        Type="String",
    )

    yield

    ssm_client.delete_parameters(
        Names=[
            f"/bigapp/production/{namespace}/database/host",
            f"/bigapp/production/{namespace}/database/password",
            f"/bigapp/development/{namespace}/my_config_value",
            f"/bigapp/development/{namespace}/products",
        ]
    )
