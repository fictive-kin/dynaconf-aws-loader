import pytest

from dynaconf_aws_loader.util import pull_from_env_or_obj, slashes_to_dict


def test_slashes_to_dict():
    """
    Convert slash-delimited string key names and their values to a
    representative dictionary.

    The data we pull from AWS SSM is fomatted in this pseudo-path
    delimited fashion
    """

    data = [
        {"/app/development/database/host": "localhost"},
        {"/app/production/database/host": "db.app.com"},
        {"/app/production/database/port": "3456"},
        {"/app/production/email": "admin@fictivekin.com"},
        {"/app/production/stripe_products": '{"monthly": "abc", "yearly": 123}'},
        {"/other-app/development/database/host": "127.0.0.1"},
    ]

    results = slashes_to_dict(data)

    assert results == {
        "app": {
            "development": {"database": {"host": "localhost"}},
            "production": {
                "database": {"host": "db.app.com", "port": "3456"},
                "email": "admin@fictivekin.com",
                "stripe_products": '{"monthly": "abc", "yearly": ' "123}",
            },
        },
        "other-app": {"development": {"database": {"host": "127.0.0.1"}}},
    }


def test_pull_from_env_or_obj(blank_settings):
    """
    Get value from env (dict-like object) or passed settings, and
    conditionally set this value on the settings.
    """

    env = {"key1": "value1", "key2": "value2"}

    result = pull_from_env_or_obj(key_name="key1", env=env, obj=blank_settings)

    assert result == "value1"
    assert blank_settings.key1 == "value1"
