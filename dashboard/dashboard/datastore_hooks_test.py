# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from google.appengine.ext import ndb

from dashboard import datastore_hooks
from dashboard import testing_common
from dashboard import utils
from dashboard.models import graph_data
from dashboard.models import sheriff


class FakeRequest(object):

  def __init__(self):
    self.registry = {}


class DatastoreHooksTest(testing_common.TestCase):

  def setUp(self):
    super(DatastoreHooksTest, self).setUp()
    testing_common.SetIsInternalUser('internal@chromium.org', True)
    testing_common.SetIsInternalUser('foo@chromium.org', False)
    self._AddDataToDatastore()
    datastore_hooks.InstallHooks()
    self.PatchDatastoreHooksRequest()

  def tearDown(self):
    super(DatastoreHooksTest, self).tearDown()
    self.UnsetCurrentUser()

  def _AddDataToDatastore(self):
    """Puts a set of entities; some internal-only, some not."""
    # Need to be privileged to add Test and Row objects to the datastore because
    # there is a get() for the parent_test in the pre_put_hook. This should work
    # correctly in production because Rows and Tests should only be added by
    # /add_point, which is privileged.
    self.SetCurrentUser('internal@chromium.org')
    testing_common.AddTests(
        ['ChromiumPerf'],
        ['Win7External', 'FooInternal'], {
            'TestInternal': {'SubTestInternal': {}},
            'TestExternal': {'SubTestExternal': {}},
        })
    internal_key = ['Master', 'ChromiumPerf', 'Bot', 'FooInternal']
    internal_test_key = ['Test', 'TestInternal']
    internal_sub_test_key = ['Test', 'SubTestInternal']
    external_key = ['Master', 'ChromiumPerf', 'Bot', 'Win7External']
    internal_bot = ndb.Key(*internal_key).get()
    internal_bot.internal_only = True
    internal_bot.put()
    internal_test = ndb.Key(*(external_key + internal_test_key)).get()
    internal_test.internal_only = True
    internal_test.put()
    internal_test = ndb.Key(*(internal_key + internal_test_key)).get()
    internal_test.internal_only = True
    internal_test.put()
    internal_sub_test = ndb.Key(*(
        external_key + internal_test_key + internal_sub_test_key)).get()
    internal_sub_test.internal_only = True
    internal_sub_test.put()
    internal_sub_test = ndb.Key(*(
        internal_key + internal_test_key + internal_sub_test_key)).get()
    internal_sub_test.internal_only = True
    internal_sub_test.put()

    internal_key = internal_sub_test.key
    external_key = ndb.Key(
        *(external_key + ['Test', 'TestExternal', 'Test', 'SubTestExternal']))

    internal_test_container_key = utils.GetTestContainerKey(internal_key)
    external_test_container_key = utils.GetTestContainerKey(external_key)
    for i in range(0, 100, 10):
      graph_data.Row(
          parent=internal_test_container_key, id=i, value=float(i * 2),
          internal_only=True).put()
      graph_data.Row(
          parent=external_test_container_key, id=i, value=float(i * 2)).put()
    self.UnsetCurrentUser()
    sheriff.Sheriff(
        id='external', email='foo@chromium.org', internal_only=False).put()
    sheriff.Sheriff(
        id='internal', email='internal@google.com', internal_only=True).put()

  def _CheckQueryResults(self, include_internal):
    """Asserts that the expected entities are fetched.

    The expected entities are the ones added in |_AddDataToDatastore|.

    Args:
      include_internal: Whether or not internal-only entities are included
          in the set of expected entities to be fetched.
    """
    bots = graph_data.Bot.query().fetch()
    if include_internal:
      self.assertEqual(2, len(bots))
      self.assertEqual('FooInternal', bots[0].key.string_id())
      self.assertEqual('Win7External', bots[1].key.string_id())
    else:
      self.assertEqual(1, len(bots))
      self.assertEqual('Win7External', bots[0].key.string_id())

    tests = graph_data.Test.query().fetch()
    if include_internal:
      self.assertEqual(8, len(tests))
      self.assertEqual('TestExternal', tests[0].key.string_id())
      self.assertEqual('SubTestExternal', tests[1].key.string_id())
      self.assertEqual('TestInternal', tests[2].key.string_id())
      self.assertEqual('SubTestInternal', tests[3].key.string_id())
      self.assertEqual('TestExternal', tests[4].key.string_id())
      self.assertEqual('SubTestExternal', tests[5].key.string_id())
      self.assertEqual('TestInternal', tests[6].key.string_id())
      self.assertEqual('SubTestInternal', tests[7].key.string_id())
    else:
      self.assertEqual(4, len(tests))
      self.assertEqual('TestExternal', tests[0].key.string_id())
      self.assertEqual('SubTestExternal', tests[1].key.string_id())
      self.assertEqual('TestExternal', tests[2].key.string_id())
      self.assertEqual('SubTestExternal', tests[3].key.string_id())

    tests = graph_data.Test.query(ancestor=ndb.Key(
        'Master', 'ChromiumPerf', 'Bot', 'FooInternal')).fetch()
    if include_internal:
      self.assertEqual(4, len(tests))
    else:
      self.assertEqual(2, len(tests))

    rows = graph_data.Row.query().fetch()
    if include_internal:
      self.assertEqual(20, len(rows))
    else:
      self.assertEqual(10, len(rows))

    rows = graph_data.Row.query(ndb.OR(
        graph_data.Row.revision < 20, graph_data.Row.revision > 70)).filter(
            graph_data.Row.value == 20).fetch()
    if include_internal:
      self.assertEqual(2, len(rows))
    else:
      self.assertEqual(1, len(rows))

    sheriffs = sheriff.Sheriff.query().fetch()
    if include_internal:
      self.assertEqual(2, len(sheriffs))
      self.assertEqual('external', sheriffs[0].key.string_id())
      self.assertEqual('foo@chromium.org', sheriffs[0].email)
      self.assertEqual('internal', sheriffs[1].key.string_id())
      self.assertEqual('internal@google.com', sheriffs[1].email)
    else:
      self.assertEqual(1, len(sheriffs))
      self.assertEqual('external', sheriffs[0].key.string_id())
      self.assertEqual('foo@chromium.org', sheriffs[0].email)

  def testQuery_NoUser_InternalOnlyNotFetched(self):
    self.UnsetCurrentUser()
    self._CheckQueryResults(include_internal=False)

  def testQuery_ExternalUser_InternalOnlyNotFetched(self):
    self.SetCurrentUser('foo@chromium.org')
    self._CheckQueryResults(include_internal=False)

  def testQuery_InternalUser_InternalOnlyFetched(self):
    self.SetCurrentUser('internal@chromium.org')
    self._CheckQueryResults(True)

  def testQuery_PrivilegedRequest_InternalOnlyFetched(self):
    self.UnsetCurrentUser()
    datastore_hooks.SetPrivilegedRequest()
    self._CheckQueryResults(True)

  def testQuery_SinglePrivilegedRequest_InternalOnlyFetched(self):
    self.UnsetCurrentUser()
    datastore_hooks.SetSinglePrivilegedRequest()
    # Not using _CheckQueryResults because this only affects a single query.
    # First query has internal results.
    rows = graph_data.Row.query().filter(graph_data.Row.value == 20).fetch()
    self.assertEqual(2, len(rows))
    # Second query does not.
    rows = graph_data.Row.query().filter(graph_data.Row.value == 20).fetch()
    self.assertEqual(1, len(rows))

  def _CheckGet(self, include_internal):
    m = ndb.Key('Master', 'ChromiumPerf').get()
    self.assertEqual(m.key.string_id(), 'ChromiumPerf')
    external_bot = ndb.Key(
        'Master', 'ChromiumPerf', 'Bot', 'Win7External').get()
    self.assertEqual(external_bot.key.string_id(), 'Win7External')
    external_bot_2 = graph_data.Bot.get_by_id('Win7External', parent=m.key)
    self.assertEqual(external_bot_2.key.string_id(), 'Win7External')
    external_test = ndb.Key(
        'Master', 'ChromiumPerf', 'Bot', 'Win7External', 'Test', 'TestExternal',
        'Test', 'SubTestExternal').get()
    self.assertEqual('SubTestExternal', external_test.key.string_id())
    if include_internal:
      internal_bot = ndb.Key(
          'Master', 'ChromiumPerf', 'Bot', 'FooInternal').get()
      self.assertEqual(internal_bot.key.string_id(), 'FooInternal')
      internal_bot_2 = graph_data.Bot.get_by_id('FooInternal', parent=m.key)
      self.assertEqual(internal_bot_2.key.string_id(), 'FooInternal')
    else:
      k = ndb.Key('Master', 'ChromiumPerf', 'Bot', 'FooInternal')
      self.assertRaises(AssertionError, k.get)
      self.assertRaises(AssertionError, graph_data.Bot.get_by_id,
                        'FooInternal', parent=m.key)
    sheriff_entity = ndb.Key('Sheriff', 'external').get()
    self.assertEqual(sheriff_entity.email, 'foo@chromium.org')
    if include_internal:
      internal_sheriff_entity = ndb.Key('Sheriff', 'internal').get()
      self.assertEqual('internal@google.com', internal_sheriff_entity.email)
    else:
      k = ndb.Key('Sheriff', 'internal')
      self.assertRaises(AssertionError, k.get)
      self.assertRaises(
          AssertionError, sheriff.Sheriff.get_by_id, 'internal')

  def testGet_NoUser(self):
    self.UnsetCurrentUser()
    self._CheckGet(include_internal=False)

  def testGet_ExternalUser(self):
    self.SetCurrentUser('foo@chromium.org')
    self._CheckGet(include_internal=False)

  def testGet_InternalUser(self):
    self.SetCurrentUser('internal@chromium.org')
    self._CheckGet(include_internal=True)

  def testGet_AdminUser(self):
    self.SetCurrentUser('foo@chromium.org', is_admin=True)
    self._CheckGet(include_internal=True)

  def testGet_PrivilegedRequest(self):
    self.UnsetCurrentUser()
    datastore_hooks.SetPrivilegedRequest()
    self._CheckGet(include_internal=True)


if __name__ == '__main__':
  unittest.main()
