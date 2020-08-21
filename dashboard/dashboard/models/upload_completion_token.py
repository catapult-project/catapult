# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""The datastore models for upload tokens and related data."""
from __future__ import absolute_import

from google.appengine.ext import ndb

from dashboard.models import internal_only_model

# Adding histogram in average takes about 5 minutes, so holding token in
# memory for 10 minutes should be enough.
_MEMCACHE_TIMEOUT = 60 * 10


class State(object):
  PENDING = 0
  PROCESSING = 1
  FAILED = 2
  COMPLETED = 3


class _StateModel(internal_only_model.InternalOnlyModel):
  state_ = ndb.IntegerProperty(
      name="state", default=State.PENDING, indexed=False)

  @classmethod
  @ndb.tasklet
  def UpdateObjectStateAsync(cls, obj, state):
    if obj is None:
      return
    yield obj.UpdateStateAsync(state)

  @ndb.tasklet
  def UpdateStateAsync(self, state):
    self.state_ = state
    yield self.put_async()

  @property
  def state(self):
    substates_keys = getattr(self, 'substates', None)
    if not substates_keys:
      return self.state_

    # "child is None" means that it was expired and removed from memcache.
    # State of such child doesn't affect parent state.
    all_states = [
        child.state
        for child in ndb.get_multi(substates_keys)
        if child is not None
    ]
    all_states.append(self.state_)
    if all(s == State.PENDING for s in all_states):
      return State.PENDING
    if any(s in (State.PROCESSING, State.PENDING) for s in all_states):
      return State.PROCESSING
    if any(s == State.FAILED for s in all_states):
      return State.FAILED
    return State.COMPLETED


class Token(_StateModel):
  """Token is used to get state of request.

  Token can contain multiple Measurement. One per each histogram in the
  request. States of nested Measurements affect state of the Token. Created
  nested measurements have PROCESSING state.

  For now, Token instances are only in memcache. Because of this, it is not
  guaranteed that the Token will be present by request completion."
  """
  _use_memcache = True
  _use_datastore = False
  _memcache_timeout = _MEMCACHE_TIMEOUT

  internal_only = ndb.BooleanProperty(default=True)

  creation_time = ndb.DateTimeProperty(auto_now_add=True, indexed=True)

  update_time = ndb.DateTimeProperty(auto_now=True, indexed=True)

  temporary_staging_file_path = ndb.StringProperty(indexed=False, default=None)

  substates = ndb.KeyProperty(repeated=True, kind='Measurement')

  def PopulateMeasurements(self, test_paths):
    """Creates measurements using list of keys.

    Should be called only once for each token. The reason is that adding a new
    measurement to the substates list is not eventual-consistent and might
    cause race conditions. But we also need to store list of keys in token
    since measurements are only in memcache.
    TODO(landrey): After entities are stored in Datastore, get rid of the
    substates list.
    """
    assert not getattr(self, 'substates',
                       None), 'Measurements have already been populated'

    measurements = [
        Measurement(state_=State.PROCESSING, id=path, parent=self.key)
        for path in test_paths
    ]
    self.substates = ndb.put_multi(measurements)
    self.put()
    return measurements


class Measurement(_StateModel):
  """Measurement represents state of added histogram.

  Measurement are keyed by the full path to the test (for example
  master/bot/test/metric/page).

  For now, Measurement instances are only in memcache. Because of this, it is
  not guaranteed that the Measurement will be present by request completion.
  """
  _use_memcache = True
  _use_datastore = False
  _memcache_timeout = _MEMCACHE_TIMEOUT

  internal_only = ndb.BooleanProperty(default=True)

  @classmethod
  @ndb.tasklet
  def UpdateStateByIdAsync(cls, model_id, state, parent_id=None):
    if model_id is None:
      return
    obj = None
    if parent_id is None:
      obj = cls.get_by_id(model_id)
    else:
      obj = cls.get_by_id(model_id, parent=ndb.Key('Token', parent_id))
    yield cls.UpdateObjectStateAsync(obj, state)
