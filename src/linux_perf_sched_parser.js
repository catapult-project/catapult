// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * @fileoverview Parses scheduler events in the Linux event trace format.
 */
base.require('linux_perf_parser');
base.exportTo('tracing', function() {

  var LinuxPerfParser = tracing.LinuxPerfParser;

  /**
   * Parses linux sched trace events.
   * @constructor
   */
  function LinuxPerfSchedParser(importer) {
    LinuxPerfParser.call(this, importer);

    importer.registerEventHandler('sched_switch',
        LinuxPerfSchedParser.prototype.schedSwitchEvent.bind(this));
    importer.registerEventHandler('sched_wakeup',
        LinuxPerfSchedParser.prototype.schedWakeupEvent.bind(this));
  }

  TestExports = {};

  // Matches the sched_switch record
  var schedSwitchRE = new RegExp(
      'prev_comm=(.+) prev_pid=(\\d+) prev_prio=(\\d+) ' +
      'prev_state=(\\S\\+?|\\S\\|\\S) ==> ' +
      'next_comm=(.+) next_pid=(\\d+) next_prio=(\\d+)');
  TestExports.schedSwitchRE = schedSwitchRE;

  // Matches the sched_wakeup record
  var schedWakeupRE =
      /comm=(.+) pid=(\d+) prio=(\d+) success=(\d+) target_cpu=(\d+)/;
  TestExports.schedWakeupRE = schedWakeupRE;

  LinuxPerfSchedParser.prototype = {
    __proto__: LinuxPerfParser.prototype,

    /**
     * Parses scheduler events and sets up state in the importer.
     */
    schedSwitchEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = schedSwitchRE.exec(eventBase[5]);
      if (!event)
        return false;

      var prevState = event[4];
      var nextComm = event[5];
      var nextPid = parseInt(event[6]);
      var nextPrio = parseInt(event[7]);

      var cpuState = this.importer.getOrCreateCpuState(cpuNumber);
      cpuState.switchRunningLinuxPid(this.importer,
          prevState, ts, nextPid, nextComm, nextPrio);
      return true;
    },

    schedWakeupEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = schedWakeupRE.exec(eventBase[5]);
      if (!event)
        return false;

      var comm = event[1];
      var pid = parseInt(event[2]);
      var prio = parseInt(event[3]);
      this.importer.markPidRunnable(ts, pid, comm, prio);
      return true;
    }
  };

  LinuxPerfParser.registerSubtype(LinuxPerfSchedParser);

  return {
    LinuxPerfSchedParser: LinuxPerfSchedParser,
    _LinuxPerfSchedParserTestExports: TestExports
  };
});
