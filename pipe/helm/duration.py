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

import re

GO_DURATION_REGEX = r'^(\d+h)?(\d+m)?(\d+(\.\d+)?s)?$'


def validate_go_duration(duration: str) -> bool:
  """assert `duration` is a valid go `Duration`"""
  # Define the regex pattern to match Go duration strings
  pattern = re.compile(GO_DURATION_REGEX)
  match = pattern.match(duration)
  return bool(match and any(group for group in match.groups() if group))

