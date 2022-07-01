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

class EKSClientFactory(object):
    def __init__(self, session):
      self._session = session
      self._sts = None

    def get_eks_client(self, region_name=None, role_arn=None, oidc_token=None, role_session_name='EKSClientFactory'):
      client_kwargs = {
        'region_name': region_name
      }

      if role_arn:
        self._sts = self._session.create_client('sts', region_name)

        if oidc_token:
            creds = self._get_role_credentials_with_web_identity(role_arn, role_session_name, oidc_token)
        else:
            creds = self._get_role_credentials(role_arn, role_session_name)

        client_kwargs['aws_access_key_id'] = creds['AccessKeyId']
        client_kwargs['aws_secret_access_key'] = creds['SecretAccessKey']
        client_kwargs['aws_session_token'] = creds['SessionToken']

      return self._session.create_client('eks', **client_kwargs)

    def _get_role_credentials(self, role_arn, role_session_name):
      return self._sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName=role_session_name
      )['Credentials']

    def _get_role_credentials_with_web_identity(self, role_arn, role_session_name, oidc_token):
      return self._sts.assume_role_with_web_identity(
        RoleArn=role_arn,
        RoleSessionName=role_session_name,
        WebIdentityToken=oidc_token
      )['Credentials']
