#!/usr/bin/env python
#
# Copyright 2010 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Quota service definition and implementation.

Contains message and service definitions for a simple quota service.  The
service maintains a set of quotas for users that can be deducted from in
a single transaction.  The requests to do this can be configured so that if
one quota check fails, none of the quota changes will take effect.

The service is configured using a QuotaConfig object and can be passed an
existing quota state (useful for if the service quits unexpectedly and is
being restored from checkpoint).  For this reason it is necessary to use
a factory instead of the default constructor.  For example:

  quota_config = QuotaConfig(
      buckets = [ QuotaBucket('DISK', 1000000),
                  QuotaBucket('EMAILS', 100, refresh_every=24 * 60 * 60),
                ])
  quota_state = {}
  quota_service = QuotaService.new_factory(quota_config, quota_state)

Every on-going request to the quota service shares the same configuration and
state objects.

Individual quota buckets can be specified to refresh to their original amounts
at regular intervals.  These intervals are specified in seconds.  The example
above specifies that the email quota is refreshed to 100 emails every day.

It is up to the client using the quota service to respond correctly to the
response of the quota service.  It does not try to raise an exception on
dential.
"""

import threading
import time

from protorpc import messages
from protorpc import remote
from protorpc import util


class QuotaCheck(messages.Message):
  """Result of checking quota of a single bucket.

  Fields:
    name: Name of quota bucket to check.
    tokens: Number of tokens to check for quota or deduct.  A negative value
      can be used to credit quota buckets.
    mode: Quota check-mode.  See Mode enumeration class for more details.
  """

  class Mode(messages.Enum):
    """Mode for individual bucket quota check.

    Values:
      ALL: All tokens must be available for consumption or else quota check
        fails and all deductions/credits are ignored.
      SOME: At least some tokens must be available for consumption.  This check
        will only fail if the remaining tokens in the bucket are already at
        zero.
      CHECK_ALL: All tokens must be available in bucket or else quota check
        fails and all other deductions/credits are ignored.  This will not cause
        a deduction to occur for the indicated bucket.
      CHECK_ALL: At least some tokens must be available in bucket or else quota
        check fails and all other deductions/credits are ignored.  This will
        not cause a deduction to occur for the indicated bucket.
    """
    ALL = 1
    SOME = 2
    CHECK_ALL = 3
    CHECK_SOME = 4

  name = messages.StringField(1, required=True)
  tokens = messages.IntegerField(2, required=True)
  mode = messages.EnumField(Mode, 3, default=Mode.ALL)


class QuotaRequest(messages.Message):
  """A request to check or deduct tokens from a users bucket.

  Fields:
    user: User to check or deduct quota for.
    quotas: Quotas to check or deduct against.
  """

  user = messages.StringField(1, required=True)
  quotas = messages.MessageField(QuotaCheck, 2, repeated=True)
  

class CheckResult(messages.Message):
  """Quota check results.

  Fields:
    status: Status of quota check for bucket.  See Status enum for details.
    available: Number of actual tokens available or consumed.  Will be
      less than the number of requested tokens when bucket has fewer
      tokens than requested.
  """

  class Status(messages.Enum):
    """Status of check result.

    Values:
      OK: All requested tokens are available or were deducted.
      SOME: Some requested tokens are available or were deducted.  This will
        cause any deductions to fail if the request mode is ALL or CHECK_ALL.
      NONE: No tokens were available.  Quota check is considered to have failed.
    """
    OK = 1
    SOME = 2
    NONE = 3

  status = messages.EnumField(Status, 1, required=True)
  available = messages.IntegerField(2, required=True)


class QuotaResponse(messages.Message):
  """ Response to QuotaRequest.

  Fields:
    all_status: Overall status of quota request.  If no quota tokens were
      available at all, this will be NONE.  If some tokens were available, even
      if some buckets had no tokens, this will be SOME.  If all tokens were
      available this will be OK.
    denied: If true, it means that some required quota check has failed.  Any
      deductions in the request will be ignored, even if those individual
      buckets had adequate tokens.
    results: Specific results of quota check for each requested bucket.  The
      names are not included as they will have a one to one correspondence with
      buckets indicated in the request.
  """

  all_status = messages.EnumField(CheckResult.Status, 1, required=True)
  denied = messages.BooleanField(2, required=True)
  results = messages.MessageField(CheckResult, 3, repeated=True)


class QuotaConfig(messages.Message):
  """Quota configuration.

  Structure used for configuring quota server.  This message is not used
  directly in the service definition, but is used to configure the
  implementation.

  Fields:
    buckets: Individual bucket configurations.  Bucket configurations are
      specified per server and are configured for any user that is requested.
  """

  class Bucket(messages.Message):
    """Individual bucket configuration.

    Fields:
      name: Bucket name.
      initial_tokens: Number of tokens initially configured for this bucket.
      refresh_every: Number of seconds after which initial tokens are restored.
        If this value is None, tokens are never restored once used, unless
        credited by the application.
    """

    name = messages.StringField(1, required=True)
    initial_tokens = messages.IntegerField(2, required=True)
    refresh_every = messages.IntegerField(4)

  buckets = messages.MessageField(Bucket, 1, repeated=True)


class QuotaStateRequest(messages.Message):
  """Request state of all quota buckets for a single user.

  Used for determining how many tokens remain in all the users quota buckets.

  Fields:
    user: The user to get buckets for.
  """

  user = messages.StringField(1, required=True)


class BucketState(messages.Message):
  """State of an individual quota bucket.

  Fields:
    name: Name of bucket.
    remaining_tokens: Number of tokens that remain in bucket.
  """

  name = messages.StringField(1, required=True)
  remaining_tokens = messages.IntegerField(2, required=True)


class QuotaStateResponse(messages.Message):
  """Response to QuotaStateRequest containing set of bucket states for user."""

  bucket_states = messages.MessageField(BucketState, 1, repeated=True)


class QuotaState(object):
  """Quota state class, used by implementation of service.

  This class is responsible for managing all the bucket states for a user.
  Quota checks and deductions must be done in the context of a transaction.  If
  a transaction fails, it can be rolled back so that the values of the
  individual buckets are preserved, even if previous checks and deductions
  succeeded.
  """

  @util.positional(3)
  def __init__(self, state, buckets):
    """Constructor.

    Args:
      state: A dictionary that is used to contain the state, mapping buckets to
        tuples (remaining_tokens, next_refresh):
          remaining_tokens: Number of tokens remaining in the bucket.
          next_refresh: Time when bucket needs to be refilled with initial
            tokens.
      buckets: A dictionary that maps buckets to BucketConfig objects.
    """
    self.__state = state
    self.__buckets = buckets

    self.__lock = threading.Lock()  # Used at transaction commit time.
    self.__transaction = threading.local()
    self.__transaction.changes = None  # Dictionary bucket -> token deduction.
                                       # Can be negative indicating credit.
    self.__transaction.time = None     # Time at which transaction began.

  def in_transaction(self):
    return self.__transaction.changes is not None

  def begin_transaction(self):
    """Begin quota transaction."""
    assert not self.in_transaction()
    self.__transaction.changes = {}
    self.__transaction.time = int(time.time())
    self.__lock.acquire()

  def commit_transaction(self):
    """Commit deductions of quota transaction."""
    assert self.in_transaction()
    for name, change in self.__transaction.changes.iteritems():
      remaining_tokens, next_refresh = self.__state[name]
      new_tokens = max(0, remaining_tokens + change)
      self.__state[name] = new_tokens, next_refresh
    self.__transaction.changes = None
    self.__lock.release()

  def abort_transaction(self):
    """Roll back transaction ignoring quota changes."""
    assert self.in_transaction()
    self.__transaction.changes = None
    self.__lock.release()

  def get_remaining_tokens(self, name):
    """Get remaining tokens for a bucket.

    This function must be called within a transaction.

    Args:
      name: Bucket name.

    Returns:
      Integer of remaining tokens in users quota bucket.
    """
    assert self.in_transaction()
    changes = self.__transaction.changes.get(name, 0)
    remaining_tokens, next_refresh = self.__state.get(name, (None, None))
    if remaining_tokens is not None and (
      next_refresh is None or
      next_refresh >= self.__transaction.time):
      return remaining_tokens + changes

    bucket = self.__buckets.get(name, None)
    if bucket is None:
      return None

    if bucket.refresh_every:
      next_refresh = self.__transaction.time + bucket.refresh_every
    else:
      next_refresh = None
    self.__state[name] = bucket.initial_tokens, next_refresh
    return bucket.initial_tokens + changes

  def check_quota(self, name, tokens):
    """Check to determine if there are enough quotas in a bucket.

    Args:
      name: Name of bucket to check.
      tokens: Number of tokens to check for availability.  Can be negative.

    Returns:
      The count of requested tokens or if insufficient, the number of tokens
      available.
    """
    assert self.in_transaction()
    assert name not in self.__transaction.changes
    remaining_tokens = self.get_remaining_tokens(name)
    if remaining_tokens is None:
      return None
    return min(tokens, remaining_tokens)

  def deduct_quota(self, name, tokens):
    """Add a quota deduction to the transaction.

    Args:
      name: Name of bucket to deduct from.
      tokens: Number of tokens to request.

    Returns:
      The count of requested tokens or if insufficient, the number of tokens
      available that will be deducted upon transaction commit.
    """
    available_tokens = self.check_quota(name, tokens)
    if available_tokens is None:
      return None
    diff = max(0, tokens - available_tokens)
    self.__transaction.changes[name] = -(tokens - diff)
    return available_tokens


class QuotaService(remote.Service):
  """Quota service."""

  __state_lock = threading.Lock()

  def __init__(self, config, states):
    """Constructor.

    NOTE: This constructor requires parameters which means a factory function
    must be used for instantiating the QuotaService.

    Args:
      config: An instance of QuotaConfig.
      states: Dictionary mapping user -> QuotaState objects.
    """
    self.__states = states
    self.__config = config
    self.__buckets = {}
    for bucket in self.__config.buckets:
      self.__buckets[bucket.name] = bucket

  def __get_state(self, user):
    """Get the state of a user.

    If no user state exists, this function will create one and store
    it for access later.

    user: User string to get quota state for.
    """
    state = self.__states.get(user, None)
    if state is None:
      state = QuotaState({}, self.__buckets)
      # TODO: Potentially problematic bottleneck.
      self.__state_lock.acquire()
      try:
        self.__states[user] = state
      finally:
        self.__state_lock.release()
    return state

  @remote.method(QuotaRequest, QuotaResponse)
  def check_quota(self, request):
    """Perform a quota check for a user."""
    state = self.__get_state(request.user)

    response = QuotaResponse(all_status=CheckResult.Status.OK)
    response.denied = False

    state.begin_transaction()
    try:
      for quota in request.quotas:
        if quota.mode in (QuotaCheck.Mode.CHECK_ALL,
                          QuotaCheck.Mode.CHECK_SOME):
          func = state.check_quota
        else:
          func = state.deduct_quota

        available = func(quota.name, quota.tokens)
        if available is None:
          raise remote.ApplicationError(
            'Unknown quota %s requested' % quota.name)

        result = CheckResult(available=available)
        response.results.append(result)
        if available == quota.tokens:
          result.status = CheckResult.Status.OK
          if response.all_status == CheckResult.Status.NONE:
            result.status = CheckResult.Status.SOME
        elif available == 0:
          result.status = CheckResult.Status.NONE
          if response.all_status == CheckResult.Status.OK:
            response.all_status = CheckResult.Status.NONE
          response.denied = True
        else:
          result.status = CheckResult.Status.SOME
          response.all_status = CheckResult.Status.SOME
          if quota.mode in (QuotaCheck.Mode.ALL, QuotaCheck.Mode.CHECK_ALL):
            response.denied = True

      if response.denied:
        state.abort_transaction()
      else:
        state.commit_transaction()
    except:
      state.abort_transaction()
      raise
    return response

  @remote.method(QuotaStateRequest, QuotaStateResponse)
  def get_quota_state(self, request):
    """Get current state of users quota buckets."""
    state = self.__get_state(request.user)

    state.begin_transaction()

    try:
      response = QuotaStateResponse()
      for name in sorted(self.__buckets.keys()):
        bucket_state = BucketState(
          name=name,
          remaining_tokens=state.get_remaining_tokens(name))
        response.bucket_states.append(bucket_state)
      return response
    finally:
      state.abort_transaction()
