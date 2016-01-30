# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from tracing import value as value_module


class Results(object):

  def __init__(self):
    self.all_values = []
    self._canonical_urls_that_have_failures = set()

  @property
  def had_failures(self):
    return len(self._canonical_urls_that_have_failures) > 0

  @property
  def failure_values(self):
    return [v for v in self.all_values
            if isinstance(v, value_module.FailureValue)]

  @property
  def skip_values(self):
    return [v for v in self.all_values
            if isinstance(v, value_module.SkipValue)]

  @property
  def all_canonical_urls(self):
    all_canonical_urls = set()
    for value in self.all_values:
      all_canonical_urls.add(value.canonical_url)
    return all_canonical_urls

  def DoesRunContainFailure(self, canonical_url):
    return canonical_url in self._canonical_urls_that_have_failures

  def AddValue(self, value):
    self.all_values.append(value)
    if isinstance(value, value_module.FailureValue):
      self._canonical_urls_that_have_failures.add(value.canonical_url)

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
    all_values_list = [v.AsDict() for v in self.all_values]
    return {
      'canonical_urls': list(self.all_canonical_urls),
      'values': all_values_list
    }
