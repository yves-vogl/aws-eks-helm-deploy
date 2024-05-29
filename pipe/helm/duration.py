import re

GO_DURATION_REGEX = r'^(\d+h)?(\d+m)?(\d+(\.\d+)?s)?$'


def validate_go_duration(duration: str) -> bool:
  """assert `duration` is a valid go `Duration`"""
  # Define the regex pattern to match Go duration strings
  pattern = re.compile(GO_DURATION_REGEX)
  match = pattern.match(duration)
  return bool(match and any(group for group in match.groups() if group))

