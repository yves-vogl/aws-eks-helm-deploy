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
from pathlib import Path

import botocore.session
import jinja2
from awscli.customizations.eks.get_token import TokenGenerator, STSClientFactory
from bitbucket_pipes_toolkit import Pipe, get_logger

try:
    from .eks.client import EKSClientFactory
    from .helm.client import HelmClient
    from .helm.error import HelmError, HelmChartNotFoundError
    from . import schema
except ImportError:
    from eks.client import EKSClientFactory
    from helm.client import HelmClient
    from helm.error import HelmError, HelmChartNotFoundError
    import schema


class HelmPipe(Pipe):
  def run(self):
    super().run()

    region_name = self.get_variable('AWS_REGION')
    role_arn = self.get_variable('ROLE_ARN')

    session_name = self.get_variable('SESSION_NAME')
    cluster_name = self.get_variable('CLUSTER_NAME')

    chart = self.get_variable('CHART')
    release_name = self.get_variable('RELEASE_NAME')
    namespace = self.get_variable('NAMESPACE')
    set = self.get_variable('SET')
    values = self.get_variable('VALUES')
    wait = self.get_variable('WAIT')
    wait = self.get_variable('DEBUG')

    session = botocore.session.get_session()

    eks_client_factory = EKSClientFactory(session)
    eks_client = eks_client_factory.get_eks_client(
      region_name=region_name,
      role_arn=role_arn,
      role_session_name=session_name
    )

    # Role Session Name is hardcoded to EKSGetTokenAuth
    # I do not patch this method for compatibility reasons
    sts_client_factory = STSClientFactory(session)
    sts_client = sts_client_factory.get_sts_client(
      region_name=region_name,
      role_arn=role_arn
    )

    cluster = eks_client.describe_cluster(name=cluster_name)
    token = TokenGenerator(sts_client).get_token(cluster_name)

    self._create_kubeconfig(cluster, token)

    # Add Bitbucket Pipeline environment
    for bitbucket_env in (
      'bitbucket_build_number',
      'bitbucket_repo_slug',
      'bitbucket_commit',
      'bitbucket_tag',
      'bitbucket_step_triggerer_uuid'
    ):
      if bitbucket_env.upper() in self.env:
        env_value = os.environ[bitbucket_env.upper()]

        if bitbucket_env == 'bitbucket_step_triggerer_uuid':
          env_value = env_value.replace('{', '').replace('}', '')

        set.append(f'"bitbucket.{bitbucket_env}={env_value}"')

    try:
      helm_client = HelmClient(chart)
      helm_client.namespace = namespace
      helm_client.release = release_name
      helm_client.set = set
      helm_client.values = values
      helm_client.wait = wait
      helm_client.debug = debug
      helm_client_result = helm_client.install()

    except HelmChartNotFoundError as error:
      self.fail(message = f'No valid helm chart found at path {error}')
    except HelmError as error:
      self.fail(message = error)

    self.success(message = helm_client_result)


  def _create_kubeconfig(self, cluster, token):

    config_path = os.path.join(Path.home(), '.kube')
    config_file = os.path.join(config_path, 'config')

    Path(config_path).mkdir(parents=True, exist_ok=True)

    template_path = f'{os.path.dirname(os.path.realpath(__file__))}/templates'
    template_loader = jinja2.FileSystemLoader(searchpath=template_path)
    template_environment = jinja2.Environment(loader=template_loader)

    template = template_environment.get_template('kube.config.j2')
    template.stream(
      certificate_authority_data=cluster["cluster"]["certificateAuthority"]["data"],
      server=cluster["cluster"]["endpoint"],
      token=token
    ).dump(config_file)

def main():
  pipe = HelmPipe(pipe_metadata='pipe.yml', schema=schema.get_schema())
  pipe.run()

if __name__ == '__main__':
  main()
