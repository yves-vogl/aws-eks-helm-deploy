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

from .error import HelmError, HelmChartNotFoundError


class HelmClient:

  chart = None
  namespace = 'kube-public'
  release = None
  set = []
  _values = []
  wait = False
  install_deps = False

  def __init__(self, chart):

    chart_yaml_path = os.path.join(
      chart,
      'Chart.yaml'
    )

    if os.path.isfile(chart_yaml_path):
      self.chart = chart
    else:
      raise HelmChartNotFoundError(chart_yaml_path)

  def install(self):

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

    if self.install_deps:
        command.append('--dependency-update')

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
