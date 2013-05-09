# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class Profiler(object):
  """A sampling profiler provided by the platform."""

  def __init__(self, output_path):
    self.output_path = output_path

  @classmethod
  def name(cls):
    """User-friendly name of this profiler."""
    raise NotImplementedError()

  @classmethod
  def is_supported(cls, options):
    """True iff this profiler is currently supported by the platform."""
    raise NotImplementedError()

  def CollectProfile(self):
    """Collect the profile from the profiler."""
    raise NotImplementedError()
