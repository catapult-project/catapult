# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mock

from google.appengine.ext import ndb

from dashboard import delete_all_entities
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import anomaly
from dashboard.models import page_state


class DeleteAllEntitiesTest(testing_common.TestCase):

  def testOnlyDeleteKind(self):
    anomaly.Anomaly(id='anomaly', test=utils.TestMetadataKey(
        'master/bot/suite/measurement')).put()
    page_state.PageState(id='page_state').put()
    self.assertEqual(1, len(ndb.Query(kind='PageState').fetch(keys_only=True)))
    self.assertEqual(1, len(ndb.Query(kind='Anomaly').fetch(keys_only=True)))

    delete_all_entities.DeleteAllEntities('PageState')
    self.assertEqual(0, len(ndb.Query(kind='PageState').fetch(keys_only=True)))
    self.assertEqual(1, len(ndb.Query(kind='Anomaly').fetch(keys_only=True)))

  def testDeleteAllViaTaskqueue(self):
    page_state.PageState(id=1).put()
    page_state.PageState(id=2).put()

    limit_patch = mock.patch.object(delete_all_entities, 'QUERY_PAGE_LIMIT', 1)
    limit_patch.start()
    self.addCleanup(limit_patch.stop)

    deferred_patch = mock.patch.object(delete_all_entities, 'deferred')
    deferred_patch.start()
    self.addCleanup(deferred_patch.stop)

    delete_all_entities.DeleteAllEntities('PageState')
    self.assertEqual(1, len(ndb.Query(kind='PageState').fetch(keys_only=True)))
    delete_all_entities.deferred.defer.assert_called_once_with(
        delete_all_entities.DeleteAllEntities, 'PageState')

  def testRequireKind(self):
    with self.assertRaises(ValueError):
      delete_all_entities.DeleteAllEntities('')
