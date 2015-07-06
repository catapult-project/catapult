# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Functions for fetching and updating a list of top-level tests."""

import logging

from google.appengine.api import datastore_errors
from google.appengine.ext import ndb

from dashboard import datastore_hooks
from dashboard import request_handler
from dashboard.models import graph_data
from dashboard.models import multipart_entity


def FetchCachedTestSuites():
  """Fetches cached test suite data."""
  key = _NamespaceKey(graph_data.LIST_SUITES_CACHE_KEY)
  return multipart_entity.Get(key)


class UpdateTestSuitesHandler(request_handler.RequestHandler):
  """A simple request handler to refresh the cached test suites info."""

  def get(self):
    """Refreshes the cached test suites list."""
    self.post()

  def post(self):
    """Refreshes the cached test suites list."""
    logging.info('Going to update test suites data.')

    # Update externally-visible test suites data.
    UpdateTestSuites(datastore_hooks.EXTERNAL)

    # Update internal-only test suites data.
    datastore_hooks.SetPrivilegedRequest()
    UpdateTestSuites(datastore_hooks.INTERNAL)


def UpdateTestSuites(permissions_namespace):
  """Updates test suite data for either internal or external users."""
  logging.info('Updating test suite data for: %s', permissions_namespace)
  suite_dict = _CreateTestSuiteDict()
  key = _NamespaceKey(
      graph_data.LIST_SUITES_CACHE_KEY, namespace=permissions_namespace)
  multipart_entity.Set(key, suite_dict)


def _NamespaceKey(key, namespace=None):
  if not namespace:
    namespace = datastore_hooks.GetNamespace()
  return '%s__%s' % (namespace, key)


def _CreateTestSuiteDict():
  """Returns a dictionary with information about top-level tests.

  This method is used to generate the global JavaScript variable TEST_SUITES
  for the report page. This variable is used to initially populate the select
  menus.

  Note that there will be multiple top level Test entities for each suite name,
  since each suite name appears under multiple bots.

  Returns:
    A dictionary of the form:
      {
          'my_test_suite': {
              'masters': {'ChromiumPerf': ['mac', 'linux']},
              'monitored': ['average_commit_time/www.yahoo.com'],
          },
          ...
      }
  """
  suite_keys = _FetchTestSuiteKeys()
  suite_to_masters = _CreateSuiteMastersDict(suite_keys)
  suite_to_description = _CreateSuiteDescriptionDict(suite_keys)
  suite_to_monitored = _CreateSuiteMonitoredDict()
  result = {}
  for name in suite_to_masters:
    result[name] = {
        'masters': suite_to_masters[name],
        'monitored': suite_to_monitored.get(name, []),
        'description': suite_to_description.get(name, ''),
        'deprecated': False,
    }
  return result


def _FetchTestSuiteKeys():
  """Fetches just the keys for non-deprecated top-level Test entities."""
  # Top-level Test entities (suites) have a parent_test property set to None.
  suite_query = graph_data.Test.query(
      graph_data.Test.parent_test == None,
      graph_data.Test.deprecated == False)
  return sorted(suite_query.fetch(keys_only=True))


def _CreateSuiteMastersDict(suite_keys):
  """Returns an initial suite dict with names mapped to masters.

  Args:
    suite_keys: A list of ndb.Key entities for top-level Test entities.

  Returns:
    A dictionary mapping the test-suite names to dicts which just have
    the key "masters", the value of which is a list of dicts mapping
    master names to lists of bot names.
  """
  result = {}
  unique_names = {k.string_id() for k in suite_keys}
  for suite_name in unique_names:
    this_suite_keys = [k for k in suite_keys if k.string_id() == suite_name]
    assert this_suite_keys, 'No suite keys used for %s' % suite_name
    result[suite_name] = _MasterToBotsDict(this_suite_keys)
  return result


def _MasterToBotsDict(suite_keys):
  """Makes a dictionary listing masters and bots for some set of tests.

  Args:
    suite_keys: A collection of test suite Test keys. All of the keys in
        this set should have the same test suite name.

  Returns:
    A dictionary mapping master names to lists of bot names.
  """
  assert len({k.string_id() for k in suite_keys}) == 1

  def MasterName(key):
    return key.pairs()[0][1]

  def BotName(key):
    return key.pairs()[1][1]

  result = {}
  for master in {MasterName(k) for k in suite_keys}:
    bots = {BotName(k) for k in suite_keys if MasterName(k) == master}
    result[master] = sorted(bots)
  return result


def _CreateSuiteMonitoredDict():
  """Makes a dict of test suite names to lists of monitored sub-tests."""
  suites = _FetchSuitesWithMonitoredProperty()
  result = {}
  for suite in suites:
    name = suite.key.string_id()
    if name not in result:
      result[name] = set()
    result[name].update(map(_GetTestSubPath, suite.monitored))
  return {name: sorted(monitored) for name, monitored in result.items()}


def _FetchSuitesWithMonitoredProperty():
  """Fetches Tests with a projection query for the "monitored" property."""
  suite_query = graph_data.Test.query(
      graph_data.Test.parent_test == None,
      graph_data.Test.deprecated == False)
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
    logging.error('Timeout after fetching %d test suites.', len(suites))
  return suites


def _GetTestSubPath(key):
  """Gets the part of the test path after the suite, for the given test key.

  For example, for a test with the test path 'MyMaster/bot/my_suite/foo/bar',
  this should return 'foo/bar'.

  Args:
    key: The key of the Test entity.

  Returns:
    Slash-separated test path part after master/bot/suite.
  """
  return '/'.join(p[1] for p in key.pairs()[3:])


def _CreateSuiteDescriptionDict(suite_keys):
  """Gets a dict of test suite names to descriptions."""
  # Because of the way that descriptions are specified, all of the test suites
  # for different bots should have the same description. We only need to get
  # one entity for each test suite name.
  keys_to_get = []
  for name in {k.string_id() for k in suite_keys}:
    keys_for_name = [k for k in suite_keys if k.string_id() == name]
    keys_to_get.append(keys_for_name[0])
  tests = ndb.get_multi(keys_to_get)
  return {t.key.string_id(): t.description or '' for t in tests}
