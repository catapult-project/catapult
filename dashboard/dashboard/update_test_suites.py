# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Functions for fetching and updating a list of top-level tests."""

import logging

from google.appengine.api import datastore_errors

from dashboard import datastore_hooks
from dashboard import request_handler
from dashboard import stored_object
from dashboard.models import graph_data

# TestMetadata suite cache key.
_LIST_SUITES_CACHE_KEY = 'list_tests_get_test_suites'


def FetchCachedTestSuites():
  """Fetches cached test suite data."""
  cache_key = _NamespaceKey(_LIST_SUITES_CACHE_KEY)
  cached = stored_object.Get(cache_key)
  if cached is None:
    # If the cache test suite list is not set, update it before fetching.
    # This is for convenience when testing sending of data to a local instance.
    namespace = datastore_hooks.GetNamespace()
    UpdateTestSuites(namespace)
    cached = stored_object.Get(cache_key)
  return cached


class UpdateTestSuitesHandler(request_handler.RequestHandler):
  """A simple request handler to refresh the cached test suites info."""

  def get(self):
    """Refreshes the cached test suites list."""
    self.post()

  def post(self):
    """Refreshes the cached test suites list."""
    if self.request.get('internal_only') == 'true':
      logging.info('Going to update internal-only test suites data.')
      # Update internal-only test suites data.
      datastore_hooks.SetPrivilegedRequest()
      UpdateTestSuites(datastore_hooks.INTERNAL)
    else:
      logging.info('Going to update externally-visible test suites data.')
      # Update externally-visible test suites data.
      UpdateTestSuites(datastore_hooks.EXTERNAL)


def UpdateTestSuites(permissions_namespace):
  """Updates test suite data for either internal or external users."""
  logging.info('Updating test suite data for: %s', permissions_namespace)
  suite_dict = _CreateTestSuiteDict()
  key = _NamespaceKey(_LIST_SUITES_CACHE_KEY, namespace=permissions_namespace)
  stored_object.Set(key, suite_dict)


def _NamespaceKey(key, namespace=None):
  if not namespace:
    namespace = datastore_hooks.GetNamespace()
  return '%s__%s' % (namespace, key)


def _CreateTestSuiteDict():
  """Returns a dictionary with information about top-level tests.

  This method is used to generate the global JavaScript variable TEST_SUITES
  for the report page. This variable is used to initially populate the select
  menus.

  Note that there will be multiple top level TestMetadata entities for each
  suite name, since each suite name appears under multiple bots.

  Returns:
    A dictionary of the form:
      {
          'my_test_suite': {
              'mas': {'ChromiumPerf': {'mac': False, 'linux': False}},
              'mon': ['average_commit_time/www.yahoo.com'],
              'dep': True,
              'des': 'A description.'
          },
          ...
      }

    Where 'mas', 'mon', 'dep', and 'des' are abbreviations for 'masters',
    'monitored', 'deprecated', and 'description', respectively.
  """
  suites = _FetchSuites()
  suite_to_masters = _CreateSuiteMastersDict(suites)
  suite_to_description = _CreateSuiteDescriptionDict(suites)
  suite_to_monitored = _CreateSuiteMonitoredDict()
  nondeprecated_suites = _CreateSuiteNondeprecatedSet(suites)

  result = {}
  for name in suite_to_masters:
    result[name] = {'mas': suite_to_masters[name]}
    if name in suite_to_monitored:
      result[name]['mon'] = suite_to_monitored[name]
    if name in suite_to_description:
      result[name]['des'] = suite_to_description[name]
    if name not in nondeprecated_suites:
      result[name]['dep'] = True
  return result


def _FetchSuites():
  """Fetches Tests with deprecated and description projections."""
  suite_query = graph_data.TestMetadata.query(
      graph_data.TestMetadata.parent_test == None)
  suites = []
  cursor = None
  more = True
  try:
    while more:
      some_suites, cursor, more = suite_query.fetch_page(
          2000, start_cursor=cursor,
          projection=['deprecated', 'description'])
      suites.extend(some_suites)
  except datastore_errors.Timeout:
    logging.error('Timeout after fetching %d test suites.', len(suites))
  return suites


def _CreateSuiteMastersDict(suites):
  """Returns an initial suite dict with names mapped to masters.

  Args:
    suites: A list of entities for top-level TestMetadata entities.

  Returns:
    A dictionary mapping the test-suite names to dicts which just have
    the key "masters", the value of which is a list of dicts mapping
    master names to dict of bots.
  """
  name_to_suites = {}
  for suite in suites:
    name = suite.test_name
    if name not in name_to_suites:
      name_to_suites[name] = []
    name_to_suites[name].append(suite)

  result = {}
  for name, this_suites in name_to_suites.iteritems():
    result[name] = _MasterToBotsToDeprecatedDict(this_suites)
  return result


def _MasterToBotsToDeprecatedDict(suites):
  """Makes a dictionary listing masters, bots and deprecated for tests.

  Args:
    suites: A collection of test suite TestMetadata entities. All of the keys in
        this set should have the same test suite name.

  Returns:
    A dictionary mapping master names to bot names to deprecated.
  """
  result = {}
  for master in {s.master_name for s in suites}:
    bot = {}
    for suite in suites:
      if suite.master_name == master:
        bot[suite.bot_name] = suite.deprecated
    result[master] = bot
  return result


def _CreateSuiteMonitoredDict():
  """Makes a dict of test suite names to lists of monitored sub-tests."""
  suites = _FetchSuitesWithMonitoredProperty()
  result = {}
  for suite in suites:
    name = suite.test_name
    if name not in result:
      result[name] = set()
    result[name].update(map(_GetTestSubPath, suite.monitored))
  return {name: sorted(monitored) for name, monitored in result.items()}


def _FetchSuitesWithMonitoredProperty():
  """Fetches Tests with a projection query for the "monitored" property.

  Empty repeated properties are not indexed, so we have to make this
  query separate.
  """
  suite_query = graph_data.TestMetadata.query(
      graph_data.TestMetadata.parent_test == None)
  # Request only a certain number of entities at a time. This is meant to
  # decrease the time taken per datastore operation, to prevent timeouts,
  # but it would not decrease the total time taken.
  suites = []
  cursor = None
  more = True
  try:
    while more:
      # By experiment, it seems that fetching 2000 takes less than 2 seconds,
      # and the time-out happens after at least 10 seconds.
      some_suites, cursor, more = suite_query.fetch_page(
          2000, start_cursor=cursor, projection=['monitored'])
      suites.extend(some_suites)
  except datastore_errors.Timeout:
    logging.error('Timeout after fetching %d monitored test suites.',
                  len(suites))
  return suites


def _GetTestSubPath(key):
  """Gets the part of the test path after the suite, for the given test key.

  For example, for a test with the test path 'MyMaster/bot/my_suite/foo/bar',
  this should return 'foo/bar'.

  Args:
    key: The key of the TestMetadata entity.

  Returns:
    Slash-separated test path part after master/bot/suite.
  """
  return '/'.join(p for p in key.string_id().split('/')[3:])


def _CreateSuiteNondeprecatedSet(suites):
  """Makes a set of test suites where all are nondeprecated."""
  return {s.test_name for s in suites if not s.deprecated}


def _CreateSuiteDescriptionDict(suites):
  """Gets a dict of test suite names to descriptions."""
  # Because of the way that descriptions are specified, all of the test suites
  # for different bots should have te same description. We only need to get
  # description from one entity for each test suite name.
  results = {}
  for suite in suites:
    name = suite.test_name
    if name in results:
      continue
    if suite.description:
      results[name] = suite.description
  return results
