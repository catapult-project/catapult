# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import tempfile
import unittest
import zipfile

from profile_chrome import profiler
from profile_chrome import ui


class FakeController(object):
  def __init__(self, contents='fake-contents'):
    self.contents = contents
    self.interval = None
    self.stopped = False
    self.filename = None

  def StartTracing(self, interval):
    self.interval = interval

  def StopTracing(self):
    self.stopped = True

  def PullTrace(self):
    with tempfile.NamedTemporaryFile(delete=False) as f:
      self.filename = f.name
      f.write(self.contents)
      return f.name

  def __repr__(self):
    return 'faketrace'


class ProfilerTest(unittest.TestCase):
  def setUp(self):
    ui.EnableTestMode()

  def testCaptureBasicProfile(self):
    controller = FakeController()
    interval = 1.5
    result = profiler.CaptureProfile([controller], interval)

    try:
      self.assertEquals(controller.interval, interval)
      self.assertTrue(controller.stopped)
      self.assertTrue(os.path.exists(result))
      self.assertFalse(os.path.exists(controller.filename))
      self.assertTrue(result.endswith('.html'))
    finally:
      os.remove(result)

  def testCaptureJsonProfile(self):
    controller = FakeController()
    result = profiler.CaptureProfile([controller], 1, write_json=True)

    try:
      self.assertFalse(result.endswith('.html'))
      with open(result) as f:
        self.assertEquals(f.read(), controller.contents)
    finally:
      os.remove(result)

  def testCaptureMultipleProfiles(self):
    controllers = [FakeController('c1'), FakeController('c2')]
    result = profiler.CaptureProfile(controllers, 1, write_json=True)

    try:
      self.assertTrue(result.endswith('.zip'))
      self.assertTrue(zipfile.is_zipfile(result))
      with zipfile.ZipFile(result) as f:
        self.assertEquals(
            f.namelist(),
            [controllers[0].filename[1:], controllers[1].filename[1:]])
    finally:
      os.remove(result)
