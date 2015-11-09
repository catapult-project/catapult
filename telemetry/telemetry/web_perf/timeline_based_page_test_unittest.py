# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import decorators
from telemetry.page import page as page_module
from telemetry.testing import browser_test_case
from telemetry.testing import options_for_unittests
from telemetry.testing import page_test_test_case
from telemetry.timeline import tracing_category_filter
from telemetry.util import wpr_modes
from telemetry.web_perf import timeline_based_measurement as tbm_module

class TestTimelinebasedMeasurementPage(page_module.Page):

  def __init__(self, ps, base_dir, trigger_animation=False,
               trigger_jank=False, trigger_slow=False,
               trigger_scroll_gesture=False):
    super(TestTimelinebasedMeasurementPage, self).__init__(
        'file://interaction_enabled_page.html', ps, base_dir)
    self._trigger_animation = trigger_animation
    self._trigger_jank = trigger_jank
    self._trigger_slow = trigger_slow
    self._trigger_scroll_gesture = trigger_scroll_gesture

  def RunPageInteractions(self, action_runner):
    if self._trigger_animation:
      action_runner.TapElement('#animating-button')
      action_runner.WaitForJavaScriptCondition('window.animationDone')
    if self._trigger_jank:
      action_runner.TapElement('#jank-button')
      action_runner.WaitForJavaScriptCondition('window.jankScriptDone')
    if self._trigger_slow:
      action_runner.TapElement('#slow-button')
      action_runner.WaitForJavaScriptCondition('window.slowScriptDone')
    if self._trigger_scroll_gesture:
      with action_runner.CreateGestureInteraction('Scroll'):
        action_runner.ScrollPage()


class TimelineBasedPageTestTest(page_test_test_case.PageTestTestCase):

  def setUp(self):
    browser_test_case.teardown_browser()
    self._options = options_for_unittests.GetCopy()
    self._options.browser_options.wpr_mode = wpr_modes.WPR_OFF

  # This test is flaky when run in parallel on the mac: crbug.com/426676
  # Also, fails on android: crbug.com/437057, and chromeos: crbug.com/483212
  @decorators.Disabled('android', 'mac', 'chromeos')
  def testSmoothnessTimelineBasedMeasurementForSmoke(self):
    ps = self.CreateEmptyPageSet()
    ps.AddStory(TestTimelinebasedMeasurementPage(
        ps, ps.base_dir, trigger_animation=True))

    tbm = tbm_module.TimelineBasedMeasurement(tbm_module.Options())
    results = self.RunMeasurement(tbm, ps, options=self._options)

    self.assertEquals(0, len(results.failures))
    v = results.FindAllPageSpecificValuesFromIRNamed(
        'CenterAnimation', 'frame_time_discrepancy')
    self.assertEquals(len(v), 1)
    v = results.FindAllPageSpecificValuesFromIRNamed(
        'DrawerAnimation', 'frame_time_discrepancy')
    self.assertEquals(len(v), 1)

  # This test should eventually work on all platforms, but currently this
  # this metric is flaky on desktop: crbug.com/453131
  @decorators.Enabled('android')
  def testGPUTimesTimelineBasedMeasurementForSmoke(self):
    ps = self.CreateEmptyPageSet()
    ps.AddStory(TestTimelinebasedMeasurementPage(
        ps, ps.base_dir, trigger_animation=True))

    cat_filter = tracing_category_filter.TracingCategoryFilter(
        'disabled-by-default-gpu.service')
    tbm_option = tbm_module.Options(overhead_level=cat_filter)
    tbm = tbm_module.TimelineBasedMeasurement(tbm_option)
    results = self.RunMeasurement(tbm, ps, options=self._options)

    self.assertEquals(0, len(results.failures))
    v = results.FindAllPageSpecificValuesFromIRNamed(
        'CenterAnimation', 'browser_compositor_max_cpu_time')
    self.assertEquals(len(v), 1)
    self.assertGreater(v[0].value, 0)
    v = results.FindAllPageSpecificValuesFromIRNamed(
        'DrawerAnimation', 'browser_compositor_max_cpu_time')
    self.assertEquals(len(v), 1)
    self.assertGreater(v[0].value, 0)

  # Disabled since mainthread_jank metric is not supported on windows platform.
  # Also, flaky on the mac when run in parallel: crbug.com/426676
  # Also, fails on android: crbug.com/437057
  # Also, fails on chromeos: crbug.com/483212
  @decorators.Disabled('android', 'win', 'mac', 'chromeos')
  def testMainthreadJankTimelineBasedMeasurement(self):
    ps = self.CreateEmptyPageSet()
    ps.AddStory(TestTimelinebasedMeasurementPage(
        ps, ps.base_dir, trigger_jank=True))

    tbm = tbm_module.TimelineBasedMeasurement(tbm_module.Options())
    results = self.RunMeasurement(tbm, ps, options=self._options)
    self.assertEquals(0, len(results.failures))

    # In interaction_enabled_page.html, we create a jank loop based on
    # window.performance.now() (basically loop for x milliseconds).
    # Since window.performance.now() uses wall-time instead of thread time,
    # we only assert the biggest jank > 50ms here to account for the fact
    # that the browser may deschedule during the jank loop.
    v = results.FindAllPageSpecificValuesFromIRNamed(
        'JankThreadJSRun', 'responsive-biggest_jank_thread_time')
    self.assertGreaterEqual(v[0].value, 50)

    v = results.FindAllPageSpecificValuesFromIRNamed(
        'JankThreadJSRun', 'responsive-total_big_jank_thread_time')
    self.assertGreaterEqual(v[0].value, 50)

  # win: crbug.com/520781, chromeos: crbug.com/483212.
  @decorators.Disabled('win', 'chromeos')
  def testTimelineBasedMeasurementGestureAdjustmentSmoke(self):
    ps = self.CreateEmptyPageSet()
    ps.AddStory(TestTimelinebasedMeasurementPage(
        ps, ps.base_dir, trigger_scroll_gesture=True))

    tbm = tbm_module.TimelineBasedMeasurement(tbm_module.Options())
    results = self.RunMeasurement(tbm, ps, options=self._options)

    self.assertEquals(0, len(results.failures))
    v = results.FindAllPageSpecificValuesFromIRNamed(
        'Gesture_Scroll', 'frame_time_discrepancy')
    self.assertEquals(len(v), 1)
