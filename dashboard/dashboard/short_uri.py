# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides an endpoint for handling storing and retrieving page states."""

import hashlib
import json

from google.appengine.ext import ndb

from dashboard import list_tests
from dashboard.common import descriptor
from dashboard.common import request_handler
from dashboard.common import datastore_hooks
from dashboard.models import page_state



class ShortUriHandler(request_handler.RequestHandler):
  """Handles short URI."""

  def get(self):
    """Handles getting page states."""
    state_id = self.request.get('sid')

    if not state_id:
      self.ReportError('Missing required parameters.', status=400)
      return

    state = ndb.Key(page_state.PageState, state_id).get()

    if not state:
      self.ReportError('Invalid sid.', status=400)
      return

    if self.request.get('v2', None) is None:
      self.response.out.write(state.value)
      return

    if state.value_v2 is None:
      state.value_v2 = _Upgrade(state.value)
      # If the user is not signed in, then they won't be able to see
      # internal_only TestMetadata, so value_v2 will be incomplete.
      # If the user is signed in, then value_v2 is complete, so it's safe to
      # store it.
      if datastore_hooks.IsUnalteredQueryPermitted():
        state.put()
    self.response.out.write(state.value_v2)

  def post(self):
    """Handles saving page states and getting state id."""

    state = self.request.get('page_state')

    if not state:
      self.ReportError('Missing required parameters.', status=400)
      return

    state_id = GetOrCreatePageState(state)

    self.response.out.write(json.dumps({'sid': state_id}))


def GetOrCreatePageState(state):
  state = state.encode('utf-8')
  state_id = GenerateHash(state)
  if not ndb.Key(page_state.PageState, state_id).get():
    page_state.PageState(id=state_id, value=state).put()
  return state_id


def GenerateHash(state_string):
  """Generates a hash for a state string."""
  return hashlib.sha256(state_string).hexdigest()


def _UpgradeChart(chart):
  groups = []
  if isinstance(chart, list):
    groups = chart
  elif isinstance(chart, dict):
    groups = chart['seriesGroups']

  suites = set()
  measurements = set()
  bots = set()
  cases = set()

  for prefix, suffixes in groups:
    if suffixes == ['all']:
      paths = list_tests.GetTestsMatchingPattern(
          prefix + '/*', only_with_rows=True)
    else:
      paths = []
      for suffix in suffixes:
        if suffix == prefix.split('/')[-1]:
          paths.append(prefix)
        else:
          paths.append(prefix + '/' + suffix)

    for path in paths:
      desc = descriptor.Descriptor.FromTestPathSync(path)
      suites.add(desc.test_suite)
      bots.add(desc.bot)
      measurements.add(desc.measurement)
      if desc.test_case:
        cases.add(desc.test_case)

  return {
      'parameters': {
          'testSuites': list(suites),
          'measurements': list(measurements),
          'bots': list(bots),
          'testCases': list(cases),
      },
  }


def _Upgrade(statejson):
  try:
    state = json.loads(statejson)
  except ValueError:
    return statejson
  if 'charts' not in state:
    return statejson
  state = {
      'showingReportSection': False,
      'chartSections': [
          _UpgradeChart(chart) for chart in state['charts']
      ],
  }
  statejson = json.dumps(state)
  return statejson
