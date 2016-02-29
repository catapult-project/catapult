# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
import time

from systrace import systrace_agent


class FtraceAgentIo(object):

  @staticmethod
  def writeFile(path, data):
    with open(path, 'w') as f:
      f.write(data)

  @staticmethod
  def readFile(path):
    with open(path, 'r') as f:
      return f.read()

  @staticmethod
  def haveWritePermissions(path):
    return os.access(path, os.W_OK)

FT_DIR = "/sys/kernel/debug/tracing/"
FT_CLOCK = FT_DIR + "trace_clock"
FT_BUFFER_SIZE = FT_DIR + "buffer_size_kb"
FT_TRACER = FT_DIR + "current_tracer"
FT_PRINT_TGID = FT_DIR + "options/print-tgid"
FT_TRACE_ON = FT_DIR + "tracing_on"
FT_TRACE = FT_DIR + "trace"
FT_TRACE_MARKER = FT_DIR + "trace_marker"
FT_OVERWRITE = FT_DIR + "options/overwrite"

all_categories = {
    "sched": {
          "desc": "CPU Scheduling",
          "req": ["sched/sched_switch/", "sched/sched_wakeup/"]
    },
    "freq": {
          "desc": "CPU Frequency",
          "req": ["power/cpu_frequency/", "power/clock_set_rate/"]
    },
    "irq": {
          "desc": "CPU IRQS and IPIS",
          "req": ["irq/"],
          "opt": ["ipi/"]
    },
    "workq": {
          "desc": "Kernel workqueues",
          "req": ["workqueue/"]
    },
    "memreclaim": {
          "desc": "Kernel Memory Reclaim",
          "req": ["vmscan/mm_vmscan_direct_reclaim_begin/",
                  "vmscan/mm_vmscan_direct_reclaim_end/",
                  "vmscan/mm_vmscan_kswapd_wake/",
                  "vmscan/mm_vmscan_kswapd_sleep/"]
    },
    "idle": {
          "desc": "CPU Idle",
          "req": ["power/cpu_idle/"]
    },
    "regulators": {
          "desc": "Voltage and Current Regulators",
          "req": ["regulator/"]
    },
    "disk": {
          "desc": "Disk I/O",
          "req": ["block/block_rq_issue/",
                  "block/block_rq_complete/"],
          "opt": ["f2fs/f2fs_sync_file_enter/",
                  "f2fs/f2fs_sync_file_exit/",
                  "f2fs/f2fs_write_begin/",
                  "f2fs/f2fs_write_end/",
                  "ext4/ext4_da_write_begin/",
                  "ext4/ext4_da_write_end/",
                  "ext4/ext4_sync_file_enter/",
                  "ext4/ext4_sync_file_exit/"]
    }
}


def try_create_agent(options, categories):
  if options.target != 'linux':
    return False
  return FtraceAgent(options, categories, FtraceAgentIo)


class FtraceAgent(systrace_agent.SystraceAgent):

  def __init__(self, options, categories, fio=FtraceAgentIo):
    """Initialize a systrace agent.

    Args:
      options: The command-line options.
      categories: The trace categories to capture.
    """
    super(FtraceAgent, self).__init__(options, categories)
    if not self._categories:
      self._categories = ["sched"]
    self._fio = fio
    self._categories = [x for x in self._categories
                        if self._is_category_available(x)]
    self._expect_trace = False

  def _get_trace_buffer_size(self):
    buffer_size = 4096
    if ((self._options.trace_buf_size is not None)
        and (self._options.trace_buf_size > 0)):
      buffer_size = self._options.trace_buf_size
    return buffer_size

  def _get_trace_time(self):
    wait_time = 5
    if ((self._options.trace_time is not None)
        and (self._options.trace_time > 0)):
      wait_time = self._options.trace_time
    return wait_time

  def start(self):
    """Start tracing.
    """
    if self._options.list_categories or len(self._categories) == 0:
      self._expect_trace = False
    else:
      self._expect_trace = True

      self._fio.writeFile(FT_BUFFER_SIZE, str(self._get_trace_buffer_size()))

      self._fio.writeFile(FT_CLOCK, 'global')
      self._fio.writeFile(FT_TRACER, 'nop')
      self._fio.writeFile(FT_OVERWRITE, "0")

      # TODO: riandrews to push necessary patches for TGID option to upstream
      # linux kernel
      # self._fio.writeFile(FT_PRINT_TGID, '1')

      for category in self._categories:
        self._category_enable(category)

      self._fio.writeFile(FT_TRACE, '')

      print "starting tracing."
      sys.stdout.flush()

      self._fio.writeFile(FT_TRACE_ON, '1')

  def collect_result(self):
    """Collect the result of tracing.

    This function will block while collecting the result. For sync mode, it
    reads the data, e.g., from stdout, until it finishes. For async mode, it
    blocks until the agent is stopped and the data is ready.
    """
    if self._options.list_categories or len(self._categories) == 0:
      self._print_avail_categories()
    else:
      try:
        time.sleep(self._get_trace_time())
      except KeyboardInterrupt:
        pass
      self._fio.writeFile(FT_TRACE_ON, '0')
      for category in self._categories:
        self._category_disable(category)
      if self._options.fix_threads:
        print "WARN: thread name fixing is not yet supported."
      if self._options.fix_tgids:
        print "WARN: tgid fixing is not yet supported."
      if self._options.fix_circular:
        print "WARN: circular buffer fixups are not yet supported."

  def expect_trace(self):
    """Check if the agent is returning a trace or not.

    This will be determined in collect_result().
    Returns:
      Whether the agent is expecting a trace or not.
    """
    return self._expect_trace

  def get_trace_data(self):
    """Get the trace data.

    Returns:
      The trace data.
    """
    d = self._fio.readFile(FT_TRACE)
    self._fio.writeFile(FT_BUFFER_SIZE, "1")
    return d

  def get_class_name(self):
    return 'trace-data'

  def _is_category_available(self, category):
    if category not in all_categories:
      return False
    events_dir = FT_DIR + "events/"
    req_events = all_categories[category]["req"]
    for event in req_events:
      event_full_path = events_dir + event + "enable"
      if not self._fio.haveWritePermissions(event_full_path):
        return False
    return True

  def _avail_categories(self):
    ret = []
    for event in all_categories:
      if self._is_category_available(event):
        ret.append(event)
    return ret

  def _print_avail_categories(self):
    avail = self._avail_categories()
    if len(avail):
      print "tracing options:"
      for category in self._avail_categories():
        desc = all_categories[category]["desc"]
        print "{0: <16}".format(category), ": ", desc
    else:
      print "No tracing categories available - perhaps you need root?"

  def _category_enable_paths(self, category):
    events_dir = FT_DIR + "events/"
    req_events = all_categories[category]["req"]
    for event in req_events:
      event_full_path = events_dir + event + "enable"
      yield event_full_path
    if "opt" in all_categories[category]:
      opt_events = all_categories[category]["opt"]
      for event in opt_events:
        event_full_path = events_dir + event + "enable"
        if self._fio.haveWritePermissions(event_full_path):
          yield event_full_path

  def _category_enable(self, category):
    for path in self._category_enable_paths(category):
      self._fio.writeFile(path, "1")

  def _category_disable(self, category):
    for path in self._category_enable_paths(category):
      self._fio.writeFile(path, "0")
