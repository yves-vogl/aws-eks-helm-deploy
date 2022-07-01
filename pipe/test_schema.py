import os
from unittest import mock
from .schema import get_schema


def test_schema_when_oidc_token_envvar_is_not_set():
    schema = get_schema()

    assert schema['AWS_ACCESS_KEY_ID']['required']
    assert schema['AWS_SECRET_ACCESS_KEY']['required']
    assert schema['ROLE_ARN']['required'] == False


@mock.patch.dict(os.environ, {'BITBUCKET_STEP_OIDC_TOKEN': 'token'})
def test_schema_when_oidc_token_envvar_is_set():
    schema = get_schema()

    assert schema['AWS_ACCESS_KEY_ID']['required'] == False
    assert schema['AWS_SECRET_ACCESS_KEY']['required'] == False
    assert schema['ROLE_ARN']['required']
