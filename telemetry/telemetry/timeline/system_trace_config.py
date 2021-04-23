# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
import json


class SystemTraceConfig(object):
  """Stores configuration options for Perfetto tracing agent.
  """

  def __init__(self):
    self._enable_chrome = False
    self._enable_power = False
    self._enable_sys_stats_cpu = False
    self._enable_ftrace_cpu = False
    self._enable_ftrace_sched = False
    self._chrome_config = None

  def GetTextConfig(self):
    text_config = """
        buffers: {
            size_kb: 200000
            fill_policy: DISCARD
        }
        duration_ms: 1800000
    """

    if self._enable_chrome:
      json_config = self._chrome_config.GetChromeTraceConfigForStartupTracing()
      # Note: The inner json.dumps is to serialize the chrome_trace_config dict
      # into a json string. The second outer json.dumps is to convert that to
      # a string literal to paste into the text proto config.
      json_config = json.dumps(
          json.dumps(json_config, sort_keys=True, separators=(',', ':')))
      text_config += """
          data_sources: {
              config {
                  name: "org.chromium.trace_event"
                  chrome_config {
                      trace_config: %s
                  }
              }
          }
          data_sources: {
              config {
                  name: "org.chromium.trace_metadata"
                  chrome_config {
                      trace_config: %s
                  }
              }
          }
      """ % (json_config, json_config)

    if self._enable_power:
      text_config += """
        data_sources: {
            config {
                name: "android.power"
                android_power_config {
                    battery_poll_ms: 1000
                    battery_counters: BATTERY_COUNTER_CAPACITY_PERCENT
                    battery_counters: BATTERY_COUNTER_CHARGE
                    battery_counters: BATTERY_COUNTER_CURRENT
                    collect_power_rails: true
                }
            }
        }
    """

    if self._enable_sys_stats_cpu:
      text_config += """
          data_sources: {
              config {
                  name: "linux.sys_stats"
                  sys_stats_config {
                      stat_period_ms: 1000
                      stat_counters: STAT_CPU_TIMES
                      stat_counters: STAT_FORK_COUNT
                  }
              }
          }
      """

    if self._enable_ftrace_cpu or self._enable_ftrace_sched:
      text_config += """
        data_sources: {
            config {
                name: "linux.ftrace"
                ftrace_config {
                    ftrace_events: "power/suspend_resume"
      """

      if self._enable_ftrace_cpu:
        text_config += """
                    ftrace_events: "power/cpu_frequency"
                    ftrace_events: "power/cpu_idle"
        """

      if self._enable_ftrace_sched:
        text_config += """
                    ftrace_events: "sched/sched_switch"
                    ftrace_events: "sched/sched_process_exit"
                    ftrace_events: "sched/sched_process_free"
                    ftrace_events: "task/task_newtask"
                    ftrace_events: "task/task_rename"
        """

      text_config += "}}}\n"

    return text_config

  def EnableChrome(self, chrome_trace_config):
    self._enable_chrome = True
    self._chrome_config = chrome_trace_config

  def EnablePower(self):
    self._enable_power = True

  def EnableSysStatsCpu(self):
    self._enable_sys_stats_cpu = True

  def EnableFtraceCpu(self):
    self._enable_ftrace_cpu = True

  def EnableFtraceSched(self):
    self._enable_ftrace_sched = True
