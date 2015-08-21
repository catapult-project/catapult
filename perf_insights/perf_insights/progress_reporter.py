# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class RunReporter(object):
  def __init__(self, run_info):
    self.run_info = run_info

  def DidAddValue(self, value):
    pass

  def DidRun(self, run_failed):
    pass


# Derived from telemetry ProgressReporter. Should stay close in architecture
# to telemetry ProgressReporter.
class ProgressReporter(object):
  def WillRun(self, run_info):
    return RunReporter(run_info)

  def DidFinishAllRuns(self, results):
    pass