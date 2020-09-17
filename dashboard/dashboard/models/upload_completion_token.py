# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""The datastore models for upload tokens and related data."""
from __future__ import absolute_import

import logging

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


def StateToString(state):
  if state == State.PENDING:
    return 'PENDING'
  if state == State.PROCESSING:
    return 'PROCESSING'
  if state == State.FAILED:
    return 'FAILED'
  if state == State.COMPLETED:
    return 'COMPLETED'


class Token(internal_only_model.InternalOnlyModel):
  """Token is used to get state of request.

  Token can contain multiple Measurement. One per each histogram in the
  request. States of nested Measurements affect state of the Token.

  For now, Token instances are only in memcache. Because of this, it is not
  guaranteed that the Token will be present by request completion."
  """
  _use_memcache = True
  _use_datastore = False
  _memcache_timeout = _MEMCACHE_TIMEOUT

  internal_only = ndb.BooleanProperty(default=True)

  state_ = ndb.IntegerProperty(
      name='state', default=State.PENDING, indexed=False)

  creation_time = ndb.DateTimeProperty(auto_now_add=True, indexed=True)

  update_time = ndb.DateTimeProperty(auto_now=True, indexed=True)

  temporary_staging_file_path = ndb.StringProperty(indexed=False, default=None)

  substates = ndb.KeyProperty(repeated=True, kind='Measurement')

  @property
  def state(self):
    if not self.substates:
      return self.state_

    # "child is None" means that it was expired and removed from memcache.
    # State of such child doesn't affect parent state.
    all_states = [
        child.state
        for child in ndb.get_multi(self.substates)
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

  def _LogStateChanged(self):
    logging.info('Upload completion token updated. Token id: %s, state: %s',
                 self.key.id(), StateToString(self.state))

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
    self._LogStateChanged()


  def PopulateMeasurements(self, tests_monitored):
    """Creates measurements using test paths and associated measurement info.

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
        Measurement(id=path, parent=self.key, monitored=is_monitored)
        for path, is_monitored in tests_monitored.items()
    ]

    self.substates = ndb.put_multi(measurements)
    self.put()
    logging.info(
        'Upload completion token measurements created. Token id: %s, '
        'measurements: %r', self.key.id(), [m.id() for m in self.substates])
    self._LogStateChanged()
    return measurements

  def GetMeasurements(self):
    return ndb.get_multi(self.substates)


class Measurement(internal_only_model.InternalOnlyModel):
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

  state = ndb.IntegerProperty(default=State.PROCESSING, indexed=False)

  update_time = ndb.DateTimeProperty(auto_now=True, indexed=True)

  monitored = ndb.BooleanProperty(default=False, indexed=True)

  histogram = ndb.KeyProperty(kind='Histogram', indexed=True, default=None)

  @classmethod
  def GetById(cls, measurement_id, parent_id):
    if measurement_id is None or parent_id is None:
      return None
    return cls.get_by_id(measurement_id, parent=ndb.Key('Token', parent_id))

  @classmethod
  @ndb.tasklet
  def UpdateStateByIdAsync(cls, measurement_id, parent_id, state):
    obj = cls.GetById(measurement_id, parent_id)
    if obj is None:
      return
    obj.state = state
    yield obj.put_async()
    token = Token.get_by_id(parent_id)
    logging.info(
        'Upload completion token measurement updated. Token id: %s, '
        'measurement id: %s, state: %s', parent_id, measurement_id,
        StateToString(state))
    if token is not None:
      token._LogStateChanged()
    else:
      logging.info(
          'Upload completion token of the measurement is expried. Token '
          'id: %s', parent_id)
