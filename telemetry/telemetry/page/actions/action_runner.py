# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.page.actions.javascript import JavaScriptAction
from telemetry.page.actions.navigate import NavigateAction
from telemetry.web_perf import timeline_interaction_record as tir_module


class ActionRunner(object):
  def __init__(self, tab):
    self._tab = tab

  # TODO(nednguyen): remove this (or make private) when
  # crbug.com/361809 is marked fixed
  def RunAction(self, action):
    if not action.WillWaitAfterRun():
      action.WillRunAction(self._tab)
    action.RunActionAndMaybeWait(self._tab)

  def BeginInteraction(self, label, is_smooth=False, is_responsive=False):
    """Marks the beginning of an interaction record.

    An interaction record is a labeled time period containing
    interaction that developers care about. Each set of metrics
    specified in flags will be calculated for this time period.. The
    End() method in the returned object must be called once to mark
    the end of the timeline.

    Args:
      label: A label for this particular interaction. This can be any
          user-defined string, but must not contain '/'.
      is_smooth: Whether to check for smoothness metrics for this interaction.
      is_responsive: Whether to check for responsiveness metrics for
          this interaction.
    """
    flags = []
    if is_smooth:
      flags.append(tir_module.IS_SMOOTH)
    if is_responsive:
      flags.append(tir_module.IS_RESPONSIVE)

    interaction = Interaction(self._tab, label, flags)
    interaction.Begin()
    return interaction

  def NavigateToPage(self, page, timeout_seconds=None):
    """ Navigate to the given page.

    Args:
      page: page is an instance of page.Page
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

  def ExecuteJavaScript(self, js_expression):
    """Executes a given JavaScript expression.

    Example: runner.ExecuteJavaScript('var foo = 1;');

    Args:
      js_expression: The expression to execute (provided as string).
    """
    self.RunAction(JavaScriptAction({'expression': js_expression}))


class Interaction(object):
  def __init__(self, action_runner, label, flags):
    assert action_runner
    assert label
    assert isinstance(flags, list)

    self._action_runner = action_runner
    self._label = label
    self._flags = flags
    self._started = False

  def Begin(self):
    assert not self._started
    self._started = True
    self._action_runner.ExecuteJavaScript('console.time("%s");' %
        tir_module.TimelineInteractionRecord.GetJavaScriptMarker(
            self._label, self._flags))

  def End(self):
    assert self._started
    self._started = False
    self._action_runner.ExecuteJavaScript('console.timeEnd("%s");' %
        tir_module.TimelineInteractionRecord.GetJavaScriptMarker(
            self._label, self._flags))
