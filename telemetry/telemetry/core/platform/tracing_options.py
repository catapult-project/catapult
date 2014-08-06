# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class TracingOptions(object):
  """Tracing options control which core tracing systems should be enabled.

  This simply turns on those systems. If those systems have additional options,
  e.g. what to trace, then they are typically configured by adding
  categories to the TracingCategoryFilter.
  """
  def __init__(self):
    self.enable_chrome_trace = False