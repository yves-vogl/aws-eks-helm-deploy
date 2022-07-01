# Copyright @ 2020 Yves Vogl, adesso as a service GmbH
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

def get_schema():
    uuid_key = 'BITBUCKET_PIPELINE_UUID'
    build_key = 'BITBUCKET_BUILD_NUMBER'

    if uuid_key in os.environ and build_key in os.environ:
        default_session_name = f"{os.environ[uuid_key].replace('{', '').replace('}', '')}@{os.environ[build_key]}"
    else:
        default_session_name = 'BitbucketPipe'

    schema = {
        'AWS_REGION': {'type': 'string', 'required': False, 'default': 'eu-central-1'},
        'SESSION_NAME': {'type': 'string', 'required': False, 'default': default_session_name},
        'CLUSTER_NAME': {'type': 'string', 'required': True},
        'CHART': {'type': 'string', 'required': True},
        'RELEASE_NAME': {'type': 'string', 'required': False, 'nullable': True},
        'NAMESPACE': {'type': 'string', 'required': False, 'default': 'kube-public'},
        'SET': {'type': 'list', 'required': False, 'default': []},
        'VALUES': {'type': 'list', 'required': False, 'default': []},
        'WAIT': {'type': 'boolean', 'required': False, 'default': False},
        'DEBUG': {'type': 'boolean', 'required': False, 'default': False}
    }

    # This value is automatically present on a step with `oidc: true`
    oidc_token = os.getenv('BITBUCKET_STEP_OIDC_TOKEN')
    
    if oidc_token:
        schema['AWS_ACCESS_KEY_ID'] = {'type': 'string', 'required': False, 'nullable': True}
        schema['AWS_SECRET_ACCESS_KEY'] = {'type': 'string', 'required': False, 'nullable': True}
        schema['ROLE_ARN'] = {'type': 'string', 'required': True}
    else:
        schema['AWS_ACCESS_KEY_ID'] = {'type': 'string', 'required': True}
        schema['AWS_SECRET_ACCESS_KEY'] = {'type': 'string', 'required': True}
        schema['ROLE_ARN'] = {'type': 'string', 'required': False, 'nullable': True}

    return schema
