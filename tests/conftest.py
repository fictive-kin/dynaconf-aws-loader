"""
Basic test fixtures

"""

import typing as t
import os
import json
from pathlib import Path
import pytest

import boto3
from dynaconf import Dynaconf
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
def blank_settings():
    return Dynaconf()


@pytest.fixture
def basic_settings(
    tmp_path: Path, ssm_client: SSMClient
) -> t.Generator[Path, None, None]:
    """
    Basic settings with environment layers
    """

    project_name = "basic"

    data = f"""
    [default]
    SSM_PARAMETER_PROJECT_PREFIX_FOR_DYNACONF = '{project_name}'
    PRODUCT_NAME = "foobar"
    """

    ssm_client.put_parameter(
        Name=f"/{project_name}/default/products",
        # Use @json cast for Dynaconf
        # https://www.dynaconf.com/configuration/#auto_cast
        Value="@json %s" % json.dumps({"plans": ["monthly", "yearly"]}),
        Type="String",
    )
    ssm_client.put_parameter(
        Name=f"/{project_name}/development/my_config_value",
        Value="test123",
        Type="String",
    )
    ssm_client.put_parameter(
        Name=f"/{project_name}/production/database/password",
        Value="password",
        Type="SecureString",
    )
    ssm_client.put_parameter(
        Name=f"/{project_name}/production/database/host",
        Value="db.example.com",
        Type="String",
    )

    settings_file = tmp_path / "settings.toml"
    settings_file.write_text(data)

    yield settings_file

    ssm_client.delete_parameters(
        Names=[
            f"/{project_name}/production/database/host",
            f"/{project_name}/production/database/password",
            f"/{project_name}/development/my_config_value",
            f"/{project_name}/default/products",
        ]
    )


@pytest.fixture
def basic_settings_disable_default_env(
    tmp_path: Path, ssm_client: SSMClient
) -> t.Generator[Path, None, None]:
    """
    Basic settings with environment layers, with default environment disabled
    """

    project_name = "basic"

    data = f"""
    [default]
    SSM_PARAMETER_PROJECT_PREFIX_FOR_DYNACONF = '{project_name}'
    SSM_LOAD_DEFAULT_ENV_FOR_DYNACONF = false
    PRODUCT_NAME = "foobar"
    """

    # We'll set some default values, just to ensure that our loader does not
    # access them.
    ssm_client.put_parameter(
        Name=f"/{project_name}/default/products",
        # Use @json cast for Dynaconf
        # https://www.dynaconf.com/configuration/#auto_cast
        Value="@json %s" % json.dumps({"plans": ["monthly", "yearly"]}),
        Type="String",
    )
    ssm_client.put_parameter(
        Name=f"/{project_name}/development/my_config_value",
        Value="test123",
        Type="String",
    )
    ssm_client.put_parameter(
        Name=f"/{project_name}/production/database/password",
        Value="password",
        Type="SecureString",
    )
    ssm_client.put_parameter(
        Name=f"/{project_name}/production/database/host",
        Value="db.example.com",
        Type="String",
    )

    settings_file = tmp_path / "settings.toml"
    settings_file.write_text(data)

    yield settings_file

    ssm_client.delete_parameters(
        Names=[
            f"/{project_name}/production/database/host",
            f"/{project_name}/production/database/password",
            f"/{project_name}/development/my_config_value",
            f"/{project_name}/default/products",
        ]
    )


@pytest.fixture
def settings_without_environments(
    tmp_path: Path, ssm_client: SSMClient
) -> t.Generator[Path, None, None]:
    """
    Basic settings without environment layering
    """

    project_name = "basic-envless"
    data = f"""
    SSM_PARAMETER_PROJECT_PREFIX_FOR_DYNACONF = '{project_name}'
    PRODUCT_NAME = "foobar"
    """

    ssm_client.put_parameter(
        Name=f"/{project_name}/default/products",
        # Use @json cast for Dynaconf
        # https://www.dynaconf.com/configuration/#auto_cast
        Value="@json %s" % json.dumps({"plans": ["monthly", "yearly"]}),
        Type="String",
    )
    ssm_client.put_parameter(
        Name=f"/{project_name}/default/my_config_value", Value="test123", Type="String"
    )
    ssm_client.put_parameter(
        Name=f"/{project_name}/default/database/password",
        Value="password",
        Type="SecureString",
    )
    ssm_client.put_parameter(
        Name=f"/{project_name}/default/database/host",
        Value="db.example.com",
        Type="String",
    )

    settings_file = tmp_path / "settings.toml"
    settings_file.write_text(data)
    yield settings_file

    ssm_client.delete_parameters(
        Names=[
            f"/{project_name}/default/database/host",
            f"/{project_name}/default/database/password",
            f"/{project_name}/default/my_config_value",
            f"/{project_name}/default/products",
        ]
    )


@pytest.fixture
def settings_with_namespace(
    tmp_path: Path, ssm_client: SSMClient
) -> t.Generator[Path, None, None]:
    """
    Settings with environment layering _and_ namespaces
    """

    project_name = "basic-namespaced"
    namespace = "consumer"
    os.environ["SSM_PARAMETER_PROJECT_PREFIX_FOR_DYNACONF"] = project_name
    os.environ["SSM_PARAMETER_NAMESPACE_FOR_DYNACONF"] = namespace

    data = """
    [default]
    PRODUCT_NAME = "foobar"
    """

    ssm_client.put_parameter(
        Name=f"/{project_name}/development/{namespace}/products",
        # Use @json cast for Dynaconf
        # https://www.dynaconf.com/configuration/#auto_cast
        Value="@json %s" % json.dumps({"plans": ["monthly", "yearly"]}),
        Type="String",
    )
    ssm_client.put_parameter(
        Name=f"/{project_name}/development/{namespace}/my_config_value",
        Value="test123",
        Type="String",
    )
    ssm_client.put_parameter(
        Name=f"/{project_name}/production/{namespace}/database/password",
        Value="password",
        Type="SecureString",
    )
    ssm_client.put_parameter(
        Name=f"/{project_name}/production/{namespace}/database/host",
        Value="db.example.com",
        Type="String",
    )

    settings_file = tmp_path / "settings.toml"
    settings_file.write_text(data)
    yield settings_file

    ssm_client.delete_parameters(
        Names=[
            f"/{project_name}/production/{namespace}/database/host",
            f"/{project_name}/production/{namespace}/database/password",
            f"/{project_name}/development/{namespace}/my_config_value",
            f"/{project_name}/development/{namespace}/products",
        ]
    )
    del os.environ["SSM_PARAMETER_PROJECT_PREFIX_FOR_DYNACONF"]
    del os.environ["SSM_PARAMETER_NAMESPACE_FOR_DYNACONF"]


@pytest.fixture
def settings_with_namespace_and_non_namespaced(
    tmp_path: Path, ssm_client: SSMClient
) -> t.Generator[Path, None, None]:
    """
    Layered environment settings with namespaces _and_ without namespaces
    """

    project_name = "combo"
    namespace = "pr-123"
    os.environ["SSM_PARAMETER_PROJECT_PREFIX_FOR_DYNACONF"] = project_name
    os.environ["SSM_PARAMETER_NAMESPACE_FOR_DYNACONF"] = namespace

    data = f"""
    PRODUCT_NAME = "foobar"
    """

    # Set up our regular layered environment parameters
    # #################################################

    # default, for all environments
    ssm_client.put_parameter(
        Name=f"/{project_name}/default/products",
        # Use @json cast for Dynaconf
        # https://www.dynaconf.com/configuration/#auto_cast
        Value="@json %s" % json.dumps({"plans": ["monthly", "yearly"]}),
        Type="String",
    )

    # QA environment
    ssm_client.put_parameter(
        Name=f"/{project_name}/qa/my_config_value", Value="test123", Type="String"
    )
    ssm_client.put_parameter(
        Name=f"/{project_name}/qa/database/password",
        Value="qa-password",
        Type="SecureString",
    )
    ssm_client.put_parameter(
        Name=f"/{project_name}/qa/database/host",
        Value="qa.example.com",
        Type="String",
    )

    # Production environment
    ssm_client.put_parameter(
        Name=f"/{project_name}/production/database/password",
        Value="production-password",
        Type="SecureString",
    )
    ssm_client.put_parameter(
        Name=f"/{project_name}/production/database/host",
        Value="production.example.com",
        Type="String",
    )
    ssm_client.put_parameter(
        Name=f"/{project_name}/production/region",
        Value="region-identifier",
        Type="String",
    )

    # Now for our namespaced parameters
    # #################################

    ssm_client.put_parameter(
        Name=f"/{project_name}/development/{namespace}/products",
        # Use @json cast for Dynaconf
        # https://www.dynaconf.com/configuration/#auto_cast
        Value="@json %s" % json.dumps({"plans": ["namespaced-1", "namespaced-2"]}),
        Type="String",
    )
    ssm_client.put_parameter(
        Name=f"/{project_name}/qa/{namespace}/my_config_value",
        Value="namespaced-qa-value",
        Type="String",
    )
    ssm_client.put_parameter(
        Name=f"/{project_name}/production/{namespace}/database/password",
        Value="namespaced-production-password",
        Type="SecureString",
    )
    ssm_client.put_parameter(
        Name=f"/{project_name}/production/{namespace}/database/host",
        Value="namespaced.production.example.com",
        Type="String",
    )

    settings_file = tmp_path / "settings.toml"
    settings_file.write_text(data)
    yield settings_file

    ssm_client.delete_parameters(
        Names=[
            f"/{project_name}/default/products",
            f"/{project_name}/qa/my_config_value",
            f"/{project_name}/qa/database/password",
            f"/{project_name}/qa/database/host",
            f"/{project_name}/production/database/password",
            f"/{project_name}/production/database/host",
            f"/{project_name}/production/region",
            f"/{project_name}/development/{namespace}/products",
            f"/{project_name}/qa/{namespace}/my_config_value",
            f"/{project_name}/production/{namespace}/database/password",
            f"/{project_name}/production/{namespace}/database/host",
        ]
    )

    del os.environ["SSM_PARAMETER_PROJECT_PREFIX_FOR_DYNACONF"]
    del os.environ["SSM_PARAMETER_NAMESPACE_FOR_DYNACONF"]
