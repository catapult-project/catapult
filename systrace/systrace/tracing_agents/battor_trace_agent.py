# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from os import path
import atexit
import logging
import py_utils

from battor import battor_wrapper
from devil.android import battery_utils
from devil.android import device_utils
from devil.utils import battor_device_mapping
from py_trace_event import trace_time
from systrace import tracing_agents

def try_create_agent(options):
  if options.from_file is not None:
    return False
  if options.battor:
    return BattorTraceAgent()
  return False

def _reenable_charging_if_needed(battery):
  if not battery.GetCharging():
    battery.SetCharging(True)
  logging.info('Charging status checked at exit.')

class BattorTraceAgent(tracing_agents.TracingAgent):
  # Class representing tracing agent that gets data from a BattOr.
  # BattOrs are high-frequency power monitors used for battery testing.
  def __init__(self):
    super(BattorTraceAgent, self).__init__()
    self._collection_process = None
    self._recording_error = None
    self._battor_wrapper = None
    self._battery_utils = None

  @py_utils.Timeout(tracing_agents.START_STOP_TIMEOUT)
  def StartAgentTracing(self, options, _, timeout=None):
    """Starts tracing.

    Args:
        options: Tracing options.

    Raises:
        RuntimeError: If trace already in progress.
    """
    if options.update_map or not path.isfile(options.serial_map):
      battor_device_mapping.GenerateSerialMapFile(options.serial_map,
                                                  options.hub_types)
    self._battor_wrapper = battor_wrapper.BattorWrapper(
        target_platform=options.target,
        android_device=options.device_serial_number,
        battor_path=options.battor_path,
        battor_map_file=options.serial_map)

    dev_utils = device_utils.DeviceUtils(options.device_serial_number)
    self._battery_utils = battery_utils.BatteryUtils(dev_utils)
    self._battery_utils.SetCharging(False)
    atexit.register(_reenable_charging_if_needed, self._battery_utils)
    self._battor_wrapper.StartShell()
    self._battor_wrapper.StartTracing()
    return True

  @py_utils.Timeout(tracing_agents.START_STOP_TIMEOUT)
  def StopAgentTracing(self, timeout=None):
    """Stops tracing and collects the results asynchronously.

    Creates a new process that stops the tracing and collects the results.
    Returns immediately after the process is created (does not wait for
    trace results to be collected).
    """
    self._battor_wrapper.StopTracing()
    self._battery_utils.SetCharging(True)
    return True

  def SupportsExplicitClockSync(self):
    """Returns whether this function supports explicit clock sync."""
    return self._battor_wrapper.SupportsExplicitClockSync()

  def RecordClockSyncMarker(self, sync_id, did_record_sync_marker_callback):
    """Records a clock sync marker.

    Args:
        sync_id: ID string for clock sync marker.
        did_record_sync_marker_callback: Callback function to call after
        the clock sync marker is recorded.
    """
    ts = trace_time.Now()
    self._battor_wrapper.RecordClockSyncMarker(sync_id)
    did_record_sync_marker_callback(ts, sync_id)

  @py_utils.Timeout(tracing_agents.GET_RESULTS_TIMEOUT)
  def GetResults(self, timeout=None):
    """Waits until data collection is completed and get the trace data.

    The trace data is the data that comes out of the BattOr, and is in the
    format with the following lines:

    time current voltage <sync_id>

    where the sync_id is only there if a clock sync marker was recorded
    during that sample.

    time = time since start of trace (ms)
    current = current through battery (mA) - this can be negative if the
        battery is charging
    voltage = voltage of battery (mV)

    Returns:
      The trace data.
    """
    return tracing_agents.TraceResult(
        'powerTraceAsString', self._battor_wrapper.CollectTraceData())
