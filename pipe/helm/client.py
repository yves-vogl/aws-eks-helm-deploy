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
import subprocess
from subprocess import CalledProcessError

from bitbucket_pipes_toolkit import get_logger

from .error import HelmError, HelmChartNotFoundError

logger = get_logger()


class HelmClient:

  chart = None
  namespace = 'kube-public'
  create_namespace = False
  release = None
  set = []
  _values = []
  wait = False
  install_subcharts = False

  def validate_chart(self, chart):
    """
    Validate that chart is available in correct location
    """
    chart_yaml_path = os.path.join(
      chart,
      'Chart.yaml'
    )

    if os.path.isfile(chart_yaml_path):
      self.chart = chart
    else:
      raise HelmChartNotFoundError(chart_yaml_path)

  def subcharts_install(self):
    """
    Install/Update any subcharts
    """
    command = [
      'helm',
      'dependency',
      'update',
      self.chart
    ]

    logger.info("Install subcharts")

    return self._run(command)

      
  def uninstall(self):
    """
    Run a helm uninstall. Leaves the namespace intact
    """

    command = [
      'helm',
      'uninstall',
      '--namespace',
      self.namespace,
      self.release
    ]

    return self._run(command)

  def install(self, chart):
    """
    Run a helm install
    """

    self.validate_chart(chart)
    if self.install_subcharts:
      result = self.subcharts_install()
      logger.info(result)

    command = [
      'helm',
      'upgrade'
    ]

    if self.release is not None:
      command.append(self.release)

    command += (
      self.chart,
      '--install',
      '--namespace',
      self.namespace
    )

    if self.create_namespace:
      command.append('--create-namespace')

    for set in self.set:
      command += (
        '--set',
        set
      )

    for value in self.values:
      command += (
        '--values',
        value
      )
    
    if self.wait:
        command.append('--wait')    
      
    return self._run(command)

  def _run(self, command):
    try:
      helm = subprocess.run(
        command,
        capture_output=True
      )

      helm.check_returncode()

      return helm.stdout.decode('utf-8')

    except CalledProcessError as error:
      raise HelmError(helm.stderr.decode('utf-8'))

  @property
  def values(self):
    return self._values

  @values.setter
  def values(self, value):
    for file in value:
      if not os.path.isfile(file):
        raise ValueError(f'Cannot access file {file}')
    self._values = value
