# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from perf_insights import value as value_module

class Results(object):
  def __init__(self):
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

  def AddValue(self, value):
    self.all_values.append(value)
    if isinstance(value, value_module.FailureValue):
      self._run_infos_that_have_failures.add(value.run_info)

  def Merge(self, results):
    for value in results.all_values:
      self.AddValue(value)

  def FindValueMatching(self, predicate):
    for v in self.all_values:
      if predicate(v):
        return v
    return None

  def FindValueNamed(self, name):
    return self.FindValueMatching(lambda v: v.name == name)

  def __repr__(self):
    return 'Results(%s)' % repr(self.all_values)

  def AsDict(self):
    run_dict = dict([(run_info.run_id, run_info.AsDict()) for run_info
                     in self.all_run_infos])
    all_values_list = [v.AsDict() for v in self.all_values]
    return {
      'runs': run_dict,
      'values': all_values_list
    }
