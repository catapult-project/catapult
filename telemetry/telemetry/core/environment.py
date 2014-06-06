# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class Environment(object):
  def __init__(self, base_paths, test_aliases=None):
    self._base_paths = base_paths
    if test_aliases:
      self._test_aliases = test_aliases
    else:
      self._test_aliases = {}

  @property
  def base_paths(self):
    return self._base_paths

  @property
  def test_aliases(self):
    return self._test_aliases
