# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import tempfile
import unittest
import zipfile

from profile_chrome import profiler
from profile_chrome import ui
from systrace import trace_result


class FakeAgent(object):
  def __init__(self, contents='fake-contents'):
    self.contents = contents
    self.stopped = False
    self.filename = None
    self.options = None
    self.categories = None
    self.timeout = None

  def StartAgentTracing(self, options, categories, timeout=None):
    self.options = options
    self.categories = categories
    self.timeout = timeout

  # pylint: disable=unused-argument
  def StopAgentTracing(self, timeout=None):
    self.stopped = True

  # pylint: disable=unused-argument
  def GetResults(self, timeout=None):
    trace_data = open(self.PullTrace()).read()
    return trace_result.TraceResult('fakeData', trace_data)

  def PullTrace(self):
    with tempfile.NamedTemporaryFile(delete=False) as f:
      self.filename = f.name
      f.write(self.contents)
      return f.name

  # pylint: disable=no-self-use
  def SupportsExplicitClockSync(self):
    return False

  # pylint: disable=unused-argument, no-self-use
  def RecordClockSyncMarker(self, sync_id, did_record_sync_marker_callback):
    print ('Clock sync marker cannot be recorded since explicit clock sync '
           'is not supported.')

  def __repr__(self):
    return 'faketrace'


class ProfilerTest(unittest.TestCase):
  def setUp(self):
    ui.EnableTestMode()

  def testCaptureBasicProfile(self):
    agent = FakeAgent()
    result = profiler.CaptureProfile([agent], 1)

    try:
      self.assertTrue(agent.stopped)
      self.assertTrue(os.path.exists(result))
      self.assertTrue(result.endswith('.html'))
    finally:
      if os.path.exists(result):
        os.remove(result)

  def testCaptureJsonProfile(self):
    agent = FakeAgent()
    result = profiler.CaptureProfile([agent], 1, write_json=True)

    try:
      self.assertFalse(result.endswith('.html'))
      with open(result) as f:
        self.assertEquals(f.read(), agent.contents)
    finally:
      if os.path.exists(result):
        os.remove(result)

  def testCaptureMultipleProfiles(self):
    agents = [FakeAgent('c1'), FakeAgent('c2')]
    result = profiler.CaptureProfile(agents, 1, write_json=True)

    try:
      self.assertTrue(result.endswith('.zip'))
      self.assertTrue(zipfile.is_zipfile(result))
    finally:
      if os.path.exists(result):
        os.remove(result)
