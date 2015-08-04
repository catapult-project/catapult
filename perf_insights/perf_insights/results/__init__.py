# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from perf_insights import value as value_module

class _CurrentRunState(object):
  def __init__(self, run_info):
    self.run_info = run_info
    self.has_failure = False

class Results(object):
  def __init__(self, output_formatters=None, progress_reporter=None):
    self.output_formatters = output_formatters or []
    self.progress_reporter = progress_reporter or ProgressReporter()

    self.all_values = []
    self._run_infos_that_have_failures = set()

  @property
  def had_failures(self):
    return len(self._run_infos_that_have_failures) > 0

  @property
  def failure_values(self):
    return [v for v in self.all_values
            if isinstance(v, value_module.FailureValue)]

  @property
  def skip_values(self):
    return [v for v in self.all_values
            if isinstance(v, value_module.SkipValue)]

  @property
  def all_run_infos(self):
    all_run_infos = set()
    for value in self.all_values:
      all_run_infos.add(value.run_info)
    return all_run_infos

  def DoesRunContainFailure(self, run_info):
    return run_info in self._run_infos_that_have_failures

  def WillRun(self, run_info):
    self.progress_reporter.WillRun(run_info)
    self._current_run_state = _CurrentRunState(run_info)

  def AddValue(self, value):
    assert value.run_info == self._current_run_state.run_info

    self.all_values.append(value)
    if isinstance(value, value_module.FailureValue):
      self._current_run_state.has_failure = True
      self._run_infos_that_have_failures.add(self._current_run_state.run_info)
    self.progress_reporter.DidAddValue(value)

  def DidRun(self, run_info):
    crs = self._current_run_state
    self._current_run_state = None

    self.progress_reporter.DidRun(run_info, crs.has_failure)

  def DidFinishAllRuns(self):
    self.progress_reporter.DidFinishAllRuns(self)

    for of in self.output_formatters:
      of.Format(self)
