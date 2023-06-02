from dynaconf_aws_loader.util import slashes_to_dict


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
