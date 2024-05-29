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

from unittest.mock import patch
import botocore

import pipe
from helm.duration import validate_go_duration

original_method = botocore.client.BaseClient._make_api_call

def mock_make_api_call(self, operation_name, kwarg):

  if operation_name == 'DescribeCluster':
    return {
      'cluster': {
        'endpoint': 'https://foo.example.bar',
        'certificateAuthority': {
          'data': 'abcdfef='
        }
      }
    }

  if operation_name == 'AssumeRole':
    return {
      'Credentials': {
        'AccessKeyId': 'abcdef',
        'SecretAccessKey': 'abcdef',
        'SessionToken': 'abcdef',
      }
    }

  return original_method(self, operation_name, kwarg)

def mock_helm_run(self, command):
  return ' '.join(command)

@patch('botocore.client.BaseClient._make_api_call', new=mock_make_api_call)
@patch('helm.client.HelmClient._run', new=mock_helm_run)
def test():
  pipe.main()

def test_valid_durations():
  durations = [
      "72h3m0.5s",
      "3m0.5s",
      "72h",
      "0.5s",
      "72h3m",
      "3m",
      "72h0.5s",
      ]
  validations = [validate_go_duration(d) for d in durations]
  assert all(validations), f'validation failed: results {zip(durations, validations)}'

def test_invalid_durations():
  # Test examples
  durations = [
      "72h3m0.5",
      "3m72h",
      "3m-1s",
      "72hours",
      ""
  ]
  validations = [validate_go_duration(d) for d in durations]
  assert not all(validations), f'validation failed: {zip(durations, validations)}'

tests = [test, test_valid_durations, test_invalid_durations]
[t() for t in tests]
