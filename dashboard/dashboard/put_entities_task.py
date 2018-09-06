# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint that takes a list of keys, gets them and puts them.

This is used by /edit_sheriffs, which needs to re-save all the tests that match
a pattern in order to get their _pre_put_hook to update their sheriff. However,
most of the time there are too many tests to be saved at once, so we shard it
to asynchronous tasks.

This can also be called from the interactive shell (/_ah/stats/shell) to update
entities with a field that needs to be indexed.
"""

from google.appengine.ext import ndb

from dashboard.common import datastore_hooks
from dashboard.common import request_handler


class PutEntitiesTaskHandler(request_handler.RequestHandler):

  def post(self):
    """Saves the given entities."""
    datastore_hooks.SetPrivilegedRequest()
    urlsafe_keys = self.request.get('keys').split(',')
    keys = [ndb.Key(urlsafe=k) for k in urlsafe_keys]
    results = ndb.get_multi(keys)

    tests = []
    entities = []

    for e in results:
      if e.key.kind() == 'TestMetadata':
        tests.append(e)
      else:
        entities.append(e)

    for t in tests:
      t.UpdateSheriff()
      t.put()

    ndb.put_multi(entities)
