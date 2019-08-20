# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""General functions which are useful throughout this project."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import os
import re
import time
import urllib

from apiclient import discovery
from apiclient import errors
from google.appengine.api import app_identity
from google.appengine.api import memcache
from google.appengine.api import oauth
from google.appengine.api import urlfetch
from google.appengine.api import urlfetch_errors
from google.appengine.api import users
from google.appengine.ext import ndb
import httplib2
from oauth2client import client

from dashboard.common import stored_object

SHERIFF_DOMAINS_KEY = 'sheriff_domains_key'
IP_WHITELIST_KEY = 'ip_whitelist'
SERVICE_ACCOUNT_KEY = 'service_account'
EMAIL_SCOPE = 'https://www.googleapis.com/auth/userinfo.email'
_PROJECT_ID_KEY = 'project_id'
_DEFAULT_CUSTOM_METRIC_VAL = 1
OAUTH_SCOPES = (
    'https://www.googleapis.com/auth/userinfo.email',
)
OAUTH_ENDPOINTS = ['/api/', '/add_histograms']

_AUTOROLL_DOMAINS = (
    'chops-service-accounts.iam.gserviceaccount.com',
    'skia-corp.google.com.iam.gserviceaccount.com',
    'skia-public.iam.gserviceaccount.com',
)


def IsDevAppserver():
  return app_identity.get_application_id() == 'None'


def _GetNowRfc3339():
  """Returns the current time formatted per RFC 3339."""
  return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def GetEmail():
  """Returns email address of the current user.

  Uses OAuth2 for /api/ requests, otherwise cookies.

  Returns:
    The email address as a string or None if there is no user logged in.

  Raises:
    OAuthRequestError: The request was not a valid OAuth request.
    OAuthServiceFailureError: An unknown error occurred.
  """
  request_uri = os.environ.get('REQUEST_URI', '')
  if any(request_uri.startswith(e) for e in OAUTH_ENDPOINTS):
    # Prevent a CSRF whereby a malicious site posts an api request without an
    # Authorization header (so oauth.get_current_user() is None), but while the
    # user is signed in, so their cookies would make users.get_current_user()
    # return a non-None user.
    if 'HTTP_AUTHORIZATION' not in os.environ:
      # The user is not signed in. Avoid raising OAuthRequestError.
      return None
    user = oauth.get_current_user(OAUTH_SCOPES)
  else:
    user = users.get_current_user()
  return user.email() if user else None


def TickMonitoringCustomMetric(metric_name):
  """Increments the stackdriver custom metric with the given name.

  This is used for cron job monitoring; if these metrics stop being received
  an alert mail is sent. For more information on custom metrics, see
  https://cloud.google.com/monitoring/custom-metrics/using-custom-metrics

  Args:
    metric_name: The name of the metric being monitored.
  """
  credentials = client.GoogleCredentials.get_application_default()
  monitoring = discovery.build(
      'monitoring', 'v3', credentials=credentials)
  now = _GetNowRfc3339()
  project_id = stored_object.Get(_PROJECT_ID_KEY)
  points = [{
      'interval': {
          'startTime': now,
          'endTime': now,
      },
      'value': {
          'int64Value': _DEFAULT_CUSTOM_METRIC_VAL,
      },
  }]
  write_request = monitoring.projects().timeSeries().create(
      name='projects/%s' %project_id,
      body={'timeSeries': [{
          'metric': {
              'type': 'custom.googleapis.com/%s' % metric_name,
          },
          'points': points
      }]})
  write_request.execute()


def TestPath(key):
  """Returns the test path for a TestMetadata from an ndb.Key.

  A "test path" is just a convenient string representation of an ndb.Key.
  Each test path corresponds to one ndb.Key, which can be used to get an
  entity.

  Args:
    key: An ndb.Key where all IDs are string IDs.

  Returns:
    A test path string.
  """
  if key.kind() == 'Test':
    # The Test key looks like ('Master', 'name', 'Bot', 'name', 'Test' 'name'..)
    # Pull out every other entry and join with '/' to form the path.
    return '/'.join(key.flat()[1::2])
  assert key.kind() == 'TestMetadata' or key.kind() == 'TestContainer'
  return key.id()


def TestSuiteName(test_key):
  """Returns the test suite name for a given TestMetadata key."""
  assert test_key.kind() == 'TestMetadata'
  parts = test_key.id().split('/')
  return parts[2]


def TestKey(test_path):
  """Returns the ndb.Key that corresponds to a test path."""
  if test_path is None:
    return None
  path_parts = test_path.split('/')
  if path_parts is None:
    return None
  if len(path_parts) < 3:
    key_list = [('Master', path_parts[0])]
    if len(path_parts) > 1:
      key_list += [('Bot', path_parts[1])]
    return ndb.Key(pairs=key_list)
  return ndb.Key('TestMetadata', test_path)


def TestMetadataKey(key_or_string):
  """Convert the given (Test or TestMetadata) key or test_path string to a
     TestMetadata key.

  We are in the process of converting from Test entities to TestMetadata.
  Unfortunately, we haver trillions of Row entities which have a parent_test
  property set to a Test, and it's not possible to migrate them all. So we
  use the Test key in Row queries, and convert between the old and new format.

  Note that the Test entities which the keys refer to may be deleted; the
  queries over keys still work.
  """
  if key_or_string is None:
    return None
  if isinstance(key_or_string, basestring):
    return ndb.Key('TestMetadata', key_or_string)
  if key_or_string.kind() == 'TestMetadata':
    return key_or_string
  if key_or_string.kind() == 'Test':
    return ndb.Key('TestMetadata', TestPath(key_or_string))


def OldStyleTestKey(key_or_string):
  """Get the key for the old style Test entity corresponding to this key or
     test_path.

  We are in the process of converting from Test entities to TestMetadata.
  Unfortunately, we haver trillions of Row entities which have a parent_test
  property set to a Test, and it's not possible to migrate them all. So we
  use the Test key in Row queries, and convert between the old and new format.

  Note that the Test entities which the keys refer to may be deleted; the
  queries over keys still work.
  """
  if key_or_string is None:
    return None
  elif isinstance(key_or_string, ndb.Key) and key_or_string.kind() == 'Test':
    return key_or_string
  if (isinstance(key_or_string, ndb.Key) and
      key_or_string.kind() == 'TestMetadata'):
    key_or_string = key_or_string.id()
  assert isinstance(key_or_string, basestring)
  path_parts = key_or_string.split('/')
  key_parts = ['Master', path_parts[0], 'Bot', path_parts[1]]
  for part in path_parts[2:]:
    key_parts += ['Test', part]
  return ndb.Key(*key_parts)


def MostSpecificMatchingPattern(test, pattern_data_tuples):
  """Takes a test and a list of (pattern, data) tuples and returns the data
  for the pattern which most closely matches the test. It does this by
  ordering the matching patterns, and choosing the one with the most specific
  top level match.

  For example, if there was a test Master/Bot/Foo/Bar, then:

  */*/*/Bar would match more closely than */*/*/*
  */*/*/Bar would match more closely than */*/*/Bar.*
  */*/*/Bar.* would match more closely than */*/*/*
  """

  # To implement this properly, we'll use a matcher trie. This trie data
  # structure will take the tuple of patterns like:
  #
  #   */*/*/Bar
  #   */*/*/Bar.*
  #   */*/*/*
  #
  # and create a trie of the following form:
  #
  #   (all, *) -> (all, *) -> (all, *) -> (specific, Bar)
  #                               T
  #                               + -> (partial, Bar.*)
  #                               |
  #                               + -> (all, *)
  #
  #
  # We can then traverse this trie, where we order the matchers by exactness,
  # and return the deepest pattern that matches.
  #
  # For now, we'll keep this as is.
  #
  # TODO(dberris): Refactor this to build a trie.

  matching_patterns = []
  for p, v in pattern_data_tuples:
    if not TestMatchesPattern(test, p):
      continue
    matching_patterns.append([p, v])

  if not matching_patterns:
    return None

  if isinstance(test, ndb.Key):
    test_path = TestPath(test)
  else:
    test_path = test.test_path
  test_path_parts = test_path.split('/')

  # This ensures the ordering puts the closest match at index 0
  def CmpPatterns(a, b):
    a_parts = a[0].split('/')
    b_parts = b[0].split('/')
    for a_part, b_part, test_part in reversed(
        zip(a_parts, b_parts, test_path_parts)):
      # We favour a specific match over a partial match, and a partial
      # match over a catch-all * match.
      if a_part == b_part:
        continue
      if a_part == test_part:
        return -1
      if b_part == test_part:
        return 1
      if a_part != '*':
        return -1
      if b_part != '*':
        return 1
      return 0

    # In the case when we find that the patterns are the same, we should return
    # 0 to indicate that we've found an equality.
    return 0

  matching_patterns.sort(cmp=CmpPatterns)  # pylint: disable=using-cmp-argument

  return matching_patterns[0][1]


class ParseTelemetryMetricFailed(Exception):
  pass


def ParseTelemetryMetricParts(test_path):
  """Parses a test path and returns the tir_label, measurement, and story.

  Args:
    test_path_parts: A test path.

  Returns:
    A tuple of (tir_label, measurement, story), or None if this doesn't appear
    to be a telemetry test.
  """
  test_path_parts = test_path.split('/')
  metric_parts = test_path_parts[3:]

  if len(metric_parts) > 3 or len(metric_parts) == 0:
    raise ParseTelemetryMetricFailed(test_path)

  # Normal test path structure, ie. M/B/S/foo/bar.html
  if len(metric_parts) == 2:
    return '', metric_parts[0], metric_parts[1]

  # 3 part structure, so there's a TIR label in there.
  # ie. M/B/S/timeToFirstMeaningfulPaint_avg/load_tools/load_tools_weather
  if len(metric_parts) == 3:
    return metric_parts[1], metric_parts[0], metric_parts[2]

  # Should be something like M/B/S/EventsDispatching where the trace_name is
  # left empty and implied to be summary.
  assert len(metric_parts) == 1
  return '', metric_parts[0], ''


def TestMatchesPattern(test, pattern):
  """Checks whether a test matches a test path pattern.

  Args:
    test: A TestMetadata entity or a TestMetadata key.
    pattern: A test path which can include wildcard characters (*).

  Returns:
    True if it matches, False otherwise.
  """
  if not test:
    return False
  if isinstance(test, ndb.Key):
    test_path = TestPath(test)
  else:
    test_path = test.test_path
  test_path_parts = test_path.split('/')
  pattern_parts = pattern.split('/')
  if len(test_path_parts) != len(pattern_parts):
    return False
  for test_path_part, pattern_part in zip(test_path_parts, pattern_parts):
    if not _MatchesPatternPart(pattern_part, test_path_part):
      return False
  return True


def _MatchesPatternPart(pattern_part, test_path_part):
  """Checks whether a pattern (possibly with a *) matches the given string.

  Args:
    pattern_part: A string which may contain a wildcard (*).
    test_path_part: Another string.

  Returns:
    True if it matches, False otherwise.
  """
  if pattern_part == '*' or pattern_part == test_path_part:
    return True
  if '*' not in pattern_part:
    return False
  # Escape any other special non-alphanumeric characters.
  pattern_part = re.escape(pattern_part)
  # There are not supposed to be any other asterisk characters, so all
  # occurrences of backslash-asterisk can now be replaced with dot-asterisk.
  re_pattern = re.compile('^' + pattern_part.replace('\\*', '.*') + '$')
  return re_pattern.match(test_path_part)


def TimestampMilliseconds(datetime):
  """Returns the number of milliseconds since the epoch."""
  return int(time.mktime(datetime.timetuple()) * 1000)


def GetTestContainerKey(test):
  """Gets the TestContainer key for the given TestMetadata.

  Args:
    test: Either a TestMetadata entity or its ndb.Key.

  Returns:
    ndb.Key('TestContainer', test path)
  """
  test_path = None
  if isinstance(test, ndb.Key):
    test_path = TestPath(test)
  else:
    test_path = test.test_path
  return ndb.Key('TestContainer', test_path)


def GetMulti(keys):
  """Gets a list of entities from a list of keys.

  If this user is logged in, this is the same as ndb.get_multi. However, if the
  user is logged out and any of the data is internal only, an AssertionError
  will be raised.

  Args:
    keys: A list of ndb entity keys.

  Returns:
    A list of entities, but no internal_only ones if the user is not logged in.
  """
  if IsInternalUser():
    return ndb.get_multi(keys)
  # Not logged in. Check each key individually.
  entities = []
  for key in keys:
    try:
      entities.append(key.get())
    except AssertionError:
      continue
  return entities


def MinimumAlertRange(alerts):
  """Returns the intersection of the revision ranges for a set of alerts.

  Args:
    alerts: An iterable of Alerts.

  Returns:
    A pair (start, end) if there is a valid minimum range,
    or None if the ranges are not overlapping.
  """
  ranges = [(a.start_revision, a.end_revision) for a in alerts if a]
  return MinimumRange(ranges)


def MinimumRange(ranges):
  """Returns the intersection of the given ranges, or None."""
  if not ranges:
    return None
  starts, ends = zip(*ranges)
  start, end = (max(starts), min(ends))
  if start > end:
    return None
  return start, end


def IsInternalUser():
  """Checks whether the user should be able to see internal-only data."""
  if IsDevAppserver():
    return True
  email = GetEmail()
  if not email:
    return False
  cached = GetCachedIsInternalUser(email)
  if cached is not None:
    return cached
  is_internal_user = IsGroupMember(identity=email, group='chromeperf-access')
  SetCachedIsInternalUser(email, is_internal_user)
  return is_internal_user


def IsAdministrator():
  """Checks whether the user is an administrator of the Dashboard."""
  if IsDevAppserver():
    return True
  email = GetEmail()
  if not email:
    return False
  cached = GetCachedIsAdministrator(email)
  if cached is not None:
    return cached
  is_administrator = IsGroupMember(
      identity=email, group='project-chromeperf-admins')
  SetCachedIsAdministrator(email, is_administrator)
  return is_administrator


def GetCachedIsInternalUser(email):
  return memcache.get(_IsInternalUserCacheKey(email))


def SetCachedIsInternalUser(email, value):
  memcache.add(_IsInternalUserCacheKey(email), value, time=60 * 60 * 24)


def GetCachedIsAdministrator(email):
  return memcache.get(_IsAdministratorUserCacheKey(email))


def SetCachedIsAdministrator(email, value):
  memcache.add(_IsAdministratorUserCacheKey(email), value, time=60 * 60 * 24)


def _IsInternalUserCacheKey(email):
  return 'is_internal_user_{}'.format(email)


def _IsAdministratorUserCacheKey(email):
  return 'is_administrator_{}'.format(email)


def IsGroupMember(identity, group):
  """Checks if a user is a group member of using chrome-infra-auth.appspot.com.

  Args:
    identity: User email address.
    group: Group name.

  Returns:
    True if confirmed to be a member, False otherwise.
  """
  cached = GetCachedIsGroupMember(identity, group)
  if cached is not None:
    return cached
  try:
    discovery_url = ('https://chrome-infra-auth.appspot.com'
                     '/_ah/api/discovery/v1/apis/{api}/{apiVersion}/rest')
    service = discovery.build(
        'auth', 'v1', discoveryServiceUrl=discovery_url,
        http=ServiceAccountHttp())
    request = service.membership(identity=identity, group=group)
    response = request.execute()
    is_member = response['is_member']
    SetCachedIsGroupMember(identity, group, is_member)
    return is_member
  except (errors.HttpError, KeyError, AttributeError) as e:
    logging.error('Failed to check membership of %s: %s', identity, e)
    return False


def GetCachedIsGroupMember(identity, group):
  return memcache.get(_IsGroupMemberCacheKey(identity, group))


def SetCachedIsGroupMember(identity, group, value):
  memcache.add(_IsGroupMemberCacheKey(identity, group), value, time=60*60*24)


def _IsGroupMemberCacheKey(identity, group):
  return 'is_group_member_%s_%s' % (identity, group)


def ServiceAccountHttp(scope=EMAIL_SCOPE, timeout=None):
  """Returns the Credentials of the service account if available."""
  account_details = stored_object.Get(SERVICE_ACCOUNT_KEY)
  if not account_details:
    raise KeyError('Service account credentials not found.')

  assert scope, "ServiceAccountHttp scope must not be None."

  client.logger.setLevel(logging.WARNING)
  credentials = client.SignedJwtAssertionCredentials(
      service_account_name=account_details['client_email'],
      private_key=account_details['private_key'],
      scope=scope)

  http = httplib2.Http(timeout=timeout)
  credentials.authorize(http)
  return http


def IsValidSheriffUser():
  """Checks whether the user should be allowed to triage alerts."""
  email = GetEmail()
  if not email:
    return False

  sheriff_domains = stored_object.Get(SHERIFF_DOMAINS_KEY)
  domain_matched = sheriff_domains and any(
      email.endswith('@' + domain) for domain in sheriff_domains)
  return domain_matched or IsTryjobUser()


def IsTryjobUser():
  email = GetEmail()
  return bool(email) and IsGroupMember(
      identity=email, group='project-chromium-tryjob-access')


def GetIpWhitelist():
  """Returns a list of IP address strings in the whitelist."""
  return stored_object.Get(IP_WHITELIST_KEY)


def GetRequestId():
  """Returns the request log ID which can be used to find a specific log."""
  return os.environ.get('REQUEST_LOG_ID')


def Validate(expected, actual):
  """Generic validator for expected keys, values, and types.

  Values are also considered equal if |actual| can be converted to |expected|'s
  type.  For instance:
    _Validate([3], '3')  # Returns True.

  See utils_test.py for more examples.

  Args:
    expected: Either a list of expected values or a dictionary of expected
        keys and type.  A dictionary can contain a list of expected values.
    actual: A value.
  """
  def IsValidType(expected, actual):
    if isinstance(expected, type) and not isinstance(actual, expected):
      try:
        expected(actual)
      except ValueError:
        return False
    return True

  def IsInList(expected, actual):
    for value in expected:
      try:
        if type(value)(actual) == value:
          return True
      except ValueError:
        pass
    return False

  if not expected:
    return
  expected_type = type(expected)
  actual_type = type(actual)
  if expected_type is list:
    if not IsInList(expected, actual):
      raise ValueError('Invalid value. Expected one of the following: '
                       '%s. Actual: %s.' % (','.join(expected), actual))
  elif expected_type is dict:
    if actual_type is not dict:
      raise ValueError('Invalid type. Expected: %s. Actual: %s.'
                       % (expected_type, actual_type))
    missing = set(expected.keys()) - set(actual.keys())
    if missing:
      raise ValueError('Missing the following properties: %s'
                       % ','.join(missing))
    for key in expected:
      Validate(expected[key], actual[key])
  elif not IsValidType(expected, actual):
    raise ValueError('Invalid type. Expected: %s. Actual: %s.' %
                     (expected, actual_type))


def FetchURL(request_url, skip_status_code=False):
  """Wrapper around URL fetch service to make request.

  Args:
    request_url: URL of request.
    skip_status_code: Skips return code check when True, default is False.

  Returns:
    Response object return by URL fetch, otherwise None when there's an error.
  """
  logging.info('URL being fetched: ' + request_url)
  try:
    response = urlfetch.fetch(request_url)
  except urlfetch_errors.DeadlineExceededError:
    logging.error('Deadline exceeded error checking %s', request_url)
    return None
  except urlfetch_errors.DownloadError as err:
    # DownloadError is raised to indicate a non-specific failure when there
    # was not a 4xx or 5xx status code.
    logging.error('DownloadError: %r', err)
    return None
  if skip_status_code:
    return response
  elif response.status_code != 200:
    logging.error(
        'ERROR %s checking %s', response.status_code, request_url)
    return None
  return response


def GetBuildDetailsFromStdioLink(stdio_link):
  no_details = (None, None, None, None, None)
  m = re.match(r'\[(.+?)\]\((.+?)\)', stdio_link)
  if not m:
    # This wasn't the markdown-style link we were expecting.
    return no_details
  _, link = m.groups()
  m = re.match(
      r'(https{0,1}://.*/([^\/]*)/builders/)'
      r'([^\/]+)/builds/(\d+)/steps/([^\/]+)', link)
  if not m:
    # This wasn't a buildbot formatted link.
    return no_details
  base_url, master, bot, buildnumber, step = m.groups()
  bot = urllib.unquote(bot)
  return base_url, master, bot, buildnumber, step


def GetStdioLinkFromRow(row):
  """Returns the markdown-style buildbot stdio link.

  Due to crbug.com/690630, many row entities have this set to "a_a_stdio_uri"
  instead of "a_stdio_uri".
  """
  return(getattr(row, 'a_stdio_uri', None) or
         getattr(row, 'a_a_stdio_uri', None))


def GetBuildbotStatusPageUriFromStdioLink(stdio_link):
  base_url, _, bot, buildnumber, _ = GetBuildDetailsFromStdioLink(
      stdio_link)
  if not base_url:
    # Can't parse status page
    return None
  return '%s%s/builds/%s' % (base_url, urllib.quote(bot), buildnumber)


def GetLogdogLogUriFromStdioLink(stdio_link):
  base_url, master, bot, buildnumber, step = GetBuildDetailsFromStdioLink(
      stdio_link)
  if not base_url:
    # Can't parse status page
    return None
  bot = re.sub(r'[ \(\)]', '_', bot)
  s_param = urllib.quote('chrome/bb/%s/%s/%s/+/recipes/steps/%s/0/stdout' % (
      master, bot, buildnumber, step), safe='')
  return 'https://luci-logdog.appspot.com/v/?s=%s' % s_param

def GetRowKey(testmetadata_key, revision):
  test_container_key = GetTestContainerKey(testmetadata_key)
  return ndb.Key('Row', revision, parent=test_container_key)

def GetSheriffForAutorollCommit(author, message):
  if author.split('@')[-1] not in _AUTOROLL_DOMAINS:
    # Not an autoroll.
    return None
  # This is an autoroll. The sheriff should be the first person on TBR list.
  m = re.search(r'TBR=([^,^\s]*)', message)
  if not m:
    return None
  return m.group(1)
