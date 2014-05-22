# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry.page.actions.navigate import NavigateAction
from telemetry.web_perf import timeline_interaction_record as tir_module


class ActionRunner(object):
  def __init__(self, tab):
    self._tab = tab

  #TODO(nednguyen): remove this when crbug.com/361809 is marked fixed
  def RunAction(self, action):
    if not action.WillWaitAfterRun():
      action.WillRunAction(self._tab)
    action.RunActionAndMaybeWait(self._tab)

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

  def NavigateToPage(self, page, timeout_seconds=None):
    """ Navigate to page.
        page is an instance of page.Page
    """
    if page.is_file:
      target_side_url = self._tab.browser.http_server.UrlOf(page.file_path_url)
    else:
      target_side_url = page.url
    attributes = {
      'url': target_side_url ,
      'script_to_evaluate_on_commit': page.script_to_evaluate_on_commit}
    if timeout_seconds:
      attributes['timeout_seconds'] = timeout_seconds
    self.RunAction(NavigateAction(attributes))
