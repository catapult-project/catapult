# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""The datastore models for upload tokens and related data."""
from __future__ import absolute_import

import logging

from google.appengine.ext import ndb

from dashboard.models import internal_only_model

# 10 minutes should be enough for keeping the data in memory because processing
# histograms takes 3.5 minutes in the 90th percentile.
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
  """
  _use_memcache = True
  _memcache_timeout = _MEMCACHE_TIMEOUT

  internal_only = ndb.BooleanProperty(default=True, indexed=False)

  state_ = ndb.IntegerProperty(
      name='state', default=State.PENDING, indexed=False)

  error_message = ndb.StringProperty(indexed=False, default=None)

  creation_time = ndb.DateTimeProperty(auto_now_add=True, indexed=False)

  update_time = ndb.DateTimeProperty(auto_now=True, indexed=False)

  temporary_staging_file_path = ndb.StringProperty(indexed=False, default=None)

  @property
  def state(self):
    measurements = self.GetMeasurements()
    if not measurements:
      return self.state_

    all_states = [child.state for child in measurements if child is not None]
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
  def UpdateObjectStateAsync(cls, obj, state, error_message=None):
    if obj is None:
      return
    yield obj.UpdateStateAsync(state, error_message)

  @ndb.tasklet
  def UpdateStateAsync(self, state, error_message=None):
    assert error_message is None or state == State.FAILED

    self.state_ = state
    self.error_message = error_message
    yield self.put_async()
    self._LogStateChanged()

  @ndb.tasklet
  def AddMeasurement(self, test_path, is_monitored):
    """Creates measurement, associated to the current token."""

    measurement = Measurement(
        id=test_path, parent=self.key, monitored=is_monitored)
    yield measurement.put_async()

    logging.info(
        'Upload completion token measurement created. Token id: %s, '
        'measurement id: %r', self.key.id(), measurement.key.id())
    raise ndb.Return(measurement)

  def GetMeasurements(self):
    return Measurement.query(ancestor=self.key).fetch()


class Measurement(internal_only_model.InternalOnlyModel):
  """Measurement represents state of added histogram.

  Measurement are keyed by the full path to the test (for example
  master/bot/test/metric/page) and parent token key.
  """
  _use_memcache = True
  _memcache_timeout = _MEMCACHE_TIMEOUT

  internal_only = ndb.BooleanProperty(default=True)

  state = ndb.IntegerProperty(default=State.PROCESSING, indexed=False)

  error_message = ndb.StringProperty(indexed=False, default=None)

  update_time = ndb.DateTimeProperty(auto_now=True, indexed=False)

  monitored = ndb.BooleanProperty(default=False, indexed=False)

  histogram = ndb.KeyProperty(kind='Histogram', indexed=True, default=None)

  @classmethod
  def GetById(cls, measurement_id, parent_id):
    if measurement_id is None or parent_id is None:
      return None
    return cls.get_by_id(measurement_id, parent=ndb.Key('Token', parent_id))

  @classmethod
  @ndb.tasklet
  def UpdateStateByIdAsync(cls,
                           measurement_id,
                           parent_id,
                           state,
                           error_message=None):
    assert error_message is None or state == State.FAILED

    obj = cls.GetById(measurement_id, parent_id)
    if obj is None:
      return
    obj.state = state
    obj.error_message = error_message
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
