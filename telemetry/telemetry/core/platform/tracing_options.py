# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

RECORD_AS_MUCH_AS_POSSIBLE = 'record-as-much-as-possible'
RECORD_UNTIL_FULL = 'record-until-full'
RECORD_MODES = (RECORD_AS_MUCH_AS_POSSIBLE, RECORD_UNTIL_FULL)


class TracingOptions(object):
  """Tracing options control which core tracing systems should be enabled.

  This simply turns on those systems. If those systems have additional options,
  e.g. what to trace, then they are typically configured by adding
  categories to the TracingCategoryFilter.

  Options:
         enable_chrome_trace: a boolean that specifies whether to enable
                            chrome tracing.
         record_mode: can be any mode in RECORD_MODES. This corresponds to
                    record modes in chrome (see
                    TraceRecordMode in base/debug/trace_event_impl.h for more
                    information)
  """
  def __init__(self):
    self.enable_chrome_trace = False
    self._record_mode = RECORD_AS_MUCH_AS_POSSIBLE

  @property
  def record_mode(self):  # pylint: disable=E0202
    return self._record_mode

  @record_mode.setter
  def record_mode(self, value):  # pylint: disable=E0202
    assert value in RECORD_MODES
    self._record_mode = value
