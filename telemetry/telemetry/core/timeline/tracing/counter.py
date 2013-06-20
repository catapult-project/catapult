# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class Counter(object):
  ''' Stores all the samples for a given counter.
  '''
  def __init__(self, parent, category, name):
    self.parent = parent
    self.full_name  = category + '.' + name
    self.category = category
    self.name = name
    self.samples = []
    self.timestamps = []
    self.series_names = []
    self.totals = []
    self.max_total = 0
    self._bounds = None

  @property
  def min_timestamp(self):
    if not self._bounds:
      self.UpdateBounds()
    return self._bounds[0]

  @property
  def max_timestamp(self):
    if not self._bounds:
      self.UpdateBounds()
    return self._bounds[1]

  @property
  def num_series(self):
    return len(self.series_names)

  @property
  def num_samples(self):
    return len(self.timestamps)

  def UpdateBounds(self):
    if self.num_series * self.num_samples != len(self.samples):
      raise ValueError(
          'Length of samples must be a multiple of length of timestamps.')

    self.totals = []
    self.max_total = 0
    if not len(self.samples):
      return

    self._bounds = (self.timestamps[0], self.timestamps[-1])

    max_total = None
    for i in xrange(self.num_samples):
      total = 0
      for j in xrange(self.num_series):
        total += self.samples[i * self.num_series + j]
        self.totals.append(total)
      if max_total is None or total > max_total:
        max_total = total
    self.max_total = max_total

