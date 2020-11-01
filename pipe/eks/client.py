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

    def get_eks_client(self, region_name=None, role_arn=None, role_session_name='EKSClientFactory'):
      client_kwargs = {
        'region_name': region_name
      }
      if role_arn is not None:
        creds = self._get_role_credentials(region_name, role_arn, role_session_name)
        client_kwargs['aws_access_key_id'] = creds['AccessKeyId']
        client_kwargs['aws_secret_access_key'] = creds['SecretAccessKey']
        client_kwargs['aws_session_token'] = creds['SessionToken']
      eks = self._session.create_client('eks', **client_kwargs)
      return eks

    def _get_role_credentials(self, region_name, role_arn, role_session_name):
      sts = self._session.create_client('sts', region_name)

      return sts.assume_role(
          RoleArn=role_arn,
          RoleSessionName=role_session_name
      )['Credentials']
