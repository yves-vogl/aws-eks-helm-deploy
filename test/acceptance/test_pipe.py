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

docker_image = 'andsafe/aws-eks-helm-deploy:ci-' + os.getenv('BITBUCKET_BUILD_NUMBER', 'local')

def docker_build():
  """
  Build the docker image for tests.
  :return:
  """
  args = [
    'docker',
    'build',
    '-t',
    docker_image,
    '.',
  ]
  subprocess.run(args, check=True)


def setup():
  docker_build()

def test_no_parameters():
  args = [
    'docker',
    'run',
    docker_image,
  ]

  result = subprocess.run(args, check=False, text=True, capture_output=True)
  assert result.returncode == 1
  assert 'AWS_ACCESS_KEY_ID:\n- required field' in result.stdout
  assert 'AWS_SECRET_ACCESS_KEY:\n- required field' in result.stdout
  assert 'CLUSTER_NAME:\n- required field' in result.stdout
  assert 'CHART:\n- required field' in result.stdout

def test_success(capsys):

  chart_path = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    'chart'
  )

  args = [
    'docker',
    'run',
    '-e', 'AWS_ACCESS_KEY_ID=test',
    '-e', 'AWS_SECRET_ACCESS_KEY=test',
    '-e', 'CLUSTER_NAME=test',
    '-e', 'CHART=/tmp/chart/test',
    '-e', 'RELEASE_NAME=test',
    '-e', 'NAMESPACE=test',
    '-e', 'SET_COUNT=1',
    '-e', 'SET_0="replicaCount=2"',
    '-e', 'VALUES_COUNT=1',
    '-e', 'VALUES_0=/tmp/chart/secrets.yaml',
    '-e', 'BITBUCKET_BUILD_NUMBER=1234',
    '-e', 'BITBUCKET_REPO_SLUG=test',
    '-e', 'BITBUCKET_COMMIT=abcdef',
    '-e', 'BITBUCKET_TAG=1.2.3',
    '-e', 'BITBUCKET_STEP_TRIGGERER_UUID=63edd06c-3b89-4ccb-90d5-016a88f438d8',
    '-e', 'WAIT=true',
    '-e', 'DEBUG=true',
    '-v', chart_path + ':/tmp/chart',
    docker_image,
    '/opt/pipe/test.py'
  ]

  result = subprocess.run(args, check=False, text=True, capture_output=True)

  # with capsys.disabled():
  #   print(result.stdout)

  assert 'helm upgrade test /tmp/chart/test --install' in result.stdout
  assert '--namespace test' in result.stdout
  assert '--set "replicaCount=2"' in result.stdout
  assert '--set "bitbucket.bitbucket_build_number=1234"' in result.stdout
  assert '--set "bitbucket.bitbucket_repo_slug=test"' in result.stdout
  assert '--set "bitbucket.bitbucket_commit=abcdef"' in result.stdout
  assert '--set "bitbucket.bitbucket_tag=1.2.3"' in result.stdout
  assert '--set "bitbucket.bitbucket_step_triggerer_uuid=63edd06c-3b89-4ccb-90d5-016a88f438d8"' in result.stdout
  assert '--values /tmp/chart/secrets.yaml' in result.stdout
  assert '--wait' in result.stdout
  assert '✔ helm upgrade test /tmp/chart/test --install --namespace test --set "replicaCount=2" --set "bitbucket.bitbucket_build_number=1234" --set "bitbucket.bitbucket_repo_slug=test" --set "bitbucket.bitbucket_commit=abcdef" --set "bitbucket.bitbucket_tag=1.2.3" --set "bitbucket.bitbucket_step_triggerer_uuid=63edd06c-3b89-4ccb-90d5-016a88f438d8" --values /tmp/chart/secrets.yaml' in result.stdout

  assert result.returncode == 0

def test_uninstall_schema():
    args = [
      'docker',
      'run',
      '-e', 'AWS_ACCESS_KEY_ID=test',
      '-e', 'AWS_SECRET_ACCESS_KEY=test',
      '-e', 'CLUSTER_NAME=test',
      '-e', 'RELEASE_NAME=test',
      '-e', 'NAMESPACE=test',
      '-e', 'BITBUCKET_BUILD_NUMBER=1234',
      '-e', 'BITBUCKET_REPO_SLUG=test',
      '-e', 'BITBUCKET_COMMIT=abcdef',
      '-e', 'BITBUCKET_TAG=1.2.3',
      '-e', 'BITBUCKET_STEP_TRIGGERER_UUID=63edd06c-3b89-4ccb-90d5-016a88f438d8',
      '-e', 'UNINSTALL=true',
      docker_image,
      '/opt/pipe/test.py'
    ]

    result = subprocess.run(args, check=False, text=True, capture_output=True)

    assert '--namespace test' in result.stdout
    assert '✔ helm uninstall --namespace test test' in result.stdout
