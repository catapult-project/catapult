# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Derived from telemetry ProgressReporter. Should stay close in architecture
# to telemetry ProgressReporter.
class ProgressReporter(object):
  def WillRun(self, run_info):
    pass

  def DidAddValue(self, value):
    pass

  def DidRun(self, run_info, run_failed):
    pass

  def DidFinishAllRuns(self, results):
    pass