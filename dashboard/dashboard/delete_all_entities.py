# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging

from google.appengine.ext import deferred
from google.appengine.ext import ndb


QUERY_PAGE_LIMIT = 1000


def DeleteAllEntities(kind):
  """DELETES ALL ENTITIES OF KIND |kind|.

  Args:
    kind: Required string name of model.
  """
  if not kind:
    # Query(kind='') would delete the entire datastore.
    raise ValueError('"kind" cannot be empty')

  keys, _, more = ndb.Query(kind=kind).fetch_page(
      QUERY_PAGE_LIMIT, keys_only=True)
  logging.info('Fetched %d keys; more=%r', len(keys), more)
  ndb.delete_multi(keys)
  if more:
    deferred.defer(DeleteAllEntities, kind)
