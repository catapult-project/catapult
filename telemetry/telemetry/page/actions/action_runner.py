# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry.web_perf import timeline_interaction_record as tir_module


class ActionRunner(object):
  def __init__(self, page, tab, page_test=None):
    self._page = page
    self._tab = tab
    self._page_test = page_test

  #TODO(nednguyen): remove this when crbug.com/361809 is marked fixed
  def RunAction(self, action):
    if not action.WillWaitAfterRun():
      action.WillRunAction(self._page, self._tab)
    action.RunActionAndMaybeWait(self._page, self._tab)

  def BeginInteraction(self, logical_name, flags):
    """ Issues the begin of interaction record.
        flags contains any flags in web_perf.timeline_interaction_record.
    """
    assert self._tab
    self._tab.ExecuteJavaScript('console.time("%s");' %
      tir_module.TimelineInteractionRecord.GetJavascriptMarker(logical_name,
                                                               flags))

  def EndInteraction(self, logical_name, flags):
    """ Issues the begin of interaction record.
        flags contains any flags in web_perf.timeline_interaction_record.
    """
    assert self._tab
    self._tab.ExecuteJavaScript('console.timeEnd("%s");' %
      tir_module.TimelineInteractionRecord.GetJavascriptMarker(logical_name,
                                                               flags))
