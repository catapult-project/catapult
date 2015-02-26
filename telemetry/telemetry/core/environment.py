# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class Environment(object):
  def __init__(self, base_paths, benchmark_aliases=None):
    self._base_paths = base_paths
    if benchmark_aliases:
      self._benchmark_aliases = benchmark_aliases
    else:
      self._benchmark_aliases = {}

  @property
  def base_paths(self):
    return self._base_paths

  @property
  def benchmark_aliases(self):
    return self._benchmark_aliases
