Dynaconf AWS Systems Manager Parameter Store Loader
====================================================

When configured, this loader will permit Dynaconf to query `AWS Systems Manager Parameter Store <https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html>`_ for slash-delimited hierarchical configuration data.

Loader Configuration
--------------------

An example:

.. code-block:: python

    from dynaconf import Dynaconf

    settings = Dynaconf(
        environments=True,
        settings_file="settings.toml",
        LOADERS_FOR_DYNACONF=[
            "dynaconf_aws_loader.loader",
            "dynaconf.loaders.env_loader"
        ],
    )


Note that for the basic functioning of this loader, the `environments <https://www.dynaconf.com/configuration/#environments>`_ option for ``Dynaconf`` must be set, and an environment must be used.

Configuration Variables
-----------------------

Both of the following configuration values should be set in the *environment* to avoid a chicken/egg scenario for initializing this custom loader:

- ``SSM_PARAMETER_PROJECT_PREFIX_FOR_DYNACONF``: Required.
  The ``project`` prefix in the parameter store path. For example, if the parameter hierarchy looks something like ``/baldur/development/database_uri``, then in this case ``SSM_PARAMETER_PROJECT_PREFIX_FOR_DYNACONF=baldur``.

- ``SSM_PARAMETER_NAMESPACE_FOR_DYNACONF``: Optional.
  This provides an additional level of grouping once the project and environment have been determined. For example, if the parameter hierarchy looks something like ``/baldur/pr-123/development/database_uri``, then ``SSM_PARAMETER_NAMESPACE_FOR_DYNACONF=pr-123``.

.. note::
   If a namespace is utilized, be aware that namespaced settings will be *merged* with non-namespaced settings. This merge is a naive one, where namespaced settings will completely overwrite non-namespaced settings with the same key.

The following optional variables should be set in your ``settings.toml`` (or equivalent format), if desired:

- ``SSM_ENDPOINT_URL_FOR_DYNACONF``: If your AWS SSM uses a different endpoint than the AWS default. This can be useful for local development when you are running something like `LocalStack <https://localstack.cloud/>`_.
- ``SSM_SESSION_FOR_DYNACONF``: If you require custom `boto3.session.Session <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/core/session.html>`_ arguments, you can specify then as a dictionary here. Note that this will override the default ``boto3`` credential configuration.
- ``SSM_LOAD_DEFAULT_ENV_FOR_DYNACONF``: Boolean, defaults to ``True``. If you want the SSM loader to load keys under the ``default`` environment name. The key name itself can be set via the Dynaconf setting of ``DEFAULT_ENV_FOR_DYNACONF`` if you want it to be something other than ``default``.


Parameter Store Details
~~~~~~~~~~~~~~~~~~~~~~~

The structure that this loader expects from the path-based organization in SSM is:

.. code-block::

    /<project-name>/<environment>/<parameter-name>


An optional ``namespace`` can be specified as a sub-project grouping for parameters:

.. code-block::

    /<project-name>/<environment>/<namespace>/<parameter-name>


Note that if you choose to use a ``namespace`` identifier, it must not conflict with existing ``environment`` identifiers.

If ``SSM_LOAD_DEFAULT_ENV_FOR_DYNACONF`` is set to ``True`` (which is the default value), the loader will add whatever the value of ``DEFAULT_ENV_FOR_DYNACONF`` as an ``environment`` key to load from SSM. The typical use case here is to have a default value for all environments that can be overriden on a per-environment basis as necessary.


Security Considerations
~~~~~~~~~~~~~~~~~~~~~~~

For this loader to function correctly and securely, the use of IAM policies to restrict which parameters can be read/mutated is highly encouraged.

Policies can be enacted on a glob-path basis, which will ensure that the only parameters that can be fetched/hydrated into the local object instance are the ones that the current environment is permitted to load.

The following policy for a fictional account allows a user to call the ``DescribeParameters`` and ``GetParameters`` API operations for parameters that begin with the path ``/testapp/production``:

.. code-block:: json

    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "ssm:DescribeParameters"
                ],
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "ssm:GetParameters"
                ],
                "Resource": "arn:aws:ssm:us-east-1:000000000000:parameter/testapp/production*"
            }
        ]
    }


.. warning::

    If a user has access to a path, then the user can access all levels of that path. For example, if a user has permission to access path ``/testapp``, then the user can also access ``testapp/production``. Even if a user has explicitly been denied access in IAM for parameter ``/testapp/production``, they can still call the ``GetParametersByPath`` API operation recursively for ``/testapp`` and view ``/testapp/production``.


Setting Parameters via Boto3
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Parameters may be set via the AWS Web Console UI, or one of their many client libraries. The `boto3 <https://boto3.amazonaws.com/v1/documentation/api/latest/index.html>`_ library is perhaps the most well-known, and the process is relatively straightforward:

.. code-block:: python

    import boto3
    ssm_client = boto3.client("ssm")

    ssm_client.put_parameter(
        Name="/testapp/development/database/host",
        Value="localhost",
        Type="String",
    )

    ssm_client.put_parameter(
        Name="/testapp/production/database/password",
        Value="sekrit",
        Type="SecureString",
    )

    ssm_client.put_parameter(
        Name="/testapp/production/database/host",
        Value="db.example.com",
        Type="String",
    )

    ssm_client.put_parameter(
        Name="/testapp/production/admin_email",
        Value="help@example.com",
        Type="String",
    )


This creates a parameter hierarchy with the following structure:

.. code-block:: json

    {
        "testapp": {
            "development": {"database": {"host": "localhost"}},
            "production": {
                "database": {"host": "db.example.com", "password": "sekrit"},
                "admin_email": "help@example.com",
            },
        },
    }


Parameter Name Limitations
--------------------------

AWS SSM has the following key (and thus path) limitations:

- Parameter names are case sensitive
- A parameter name must be unique within an Amazon Web Services Region
- A parameter name can't be prefixed with "aws" or "ssm" (case-insensitive)
- Parameter names can include only the following symbols and letters: a-zA-Z0-9\_.-
- The slash character ( ``/`` ) is used to delineate hierarchies in parameter names
- A parameter name can't include spaces
- Parameter hierarchies are limited to a maximum depth of fifteen levels


Testing
~~~~~~~

0. Have Docker installed and running
1. Clone this repository
2. Ensure you have `poetry` available on your system
3. `poetry run pytest`

The test suite will spin up an ephemeral Docker container; it may take a few seconds for it to load. The relevant test fixtures will handle setting parameters and their values in the Localstack SSM service.


TODO
~~~~

- [ ] CI configuration for matrix-based python/dynaconf version testing
- [ ] Handle `Parameter Store references to AWS Secrets Manager <https://docs.aws.amazon.com/systems-manager/latest/userguide/integration-ps-secretsmanager.html>`_
- [ ] Make ``tests/docker-compose.yml`` more configurable, e.g. ports, in case a different Localstack container is already running for the user
