// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * @fileoverview Parses Mali DDK/kernel events in the Linux event trace format.
 */
base.require('linux_perf_parser');
base.exportTo('tracing', function() {

  var LinuxPerfParser = tracing.LinuxPerfParser;

  /**
   * Parses Mali DDK/kernel trace events.
   * @constructor
   */
  function LinuxPerfMaliParser(importer) {
    LinuxPerfParser.call(this, importer);

    // kernel events
    importer.registerEventHandler('mali_dvfs_event',
        LinuxPerfMaliParser.prototype.dvfsEventEvent.bind(this));
    importer.registerEventHandler('mali_dvfs_set_clock',
        LinuxPerfMaliParser.prototype.dvfsSetClockEvent.bind(this));
    importer.registerEventHandler('mali_dvfs_set_voltage',
        LinuxPerfMaliParser.prototype.dvfsSetVoltageEvent.bind(this));

    // DDK events (from X server)
    importer.registerEventHandler('tracing_mark_write:mali_driver',
        LinuxPerfMaliParser.prototype.maliDDKEvent.bind(this));
  }

  LinuxPerfMaliParser.prototype = {
    __proto__: LinuxPerfParser.prototype,

    maliDDKOpenSlice: function(pid, tid, ts, func, blockinfo) {
      var thread = this.importer.model_.getOrCreateProcess(pid)
        .getOrCreateThread(tid);
      var funcArgs = /^([\w\d_]*)(?:\(\))?:?\s*(.*)$/.exec(func);
      thread.beginSlice('gpu-driver', funcArgs[1], ts,
          { 'args': funcArgs[2],
            'blockinfo': blockinfo });
    },

    maliDDKCloseSlice: function(pid, tid, ts, args, blockinfo) {
      var thread = this.importer.model_.getOrCreateProcess(pid)
        .getOrCreateThread(tid);
      if (!thread.openSliceCount) {
        // Discard unmatched ends.
        return;
      }
      thread.endSlice(ts);
    },

    /**
     * Deduce the format of Mali perf events.
     *
     * @return {RegExp} the regular expression for parsing data when the format
     * is recognized; otherwise null.
     */
    autoDetectLineRE: function(line) {
      // Matches Mali perf events with thread info
      var lineREWithThread =
        /^\s*\(([\w\-]*)\)\s*(\w+):\s*([\w\\\/\.\-]*@\d*):?\s*(.*)$/;
      if (lineREWithThread.test(line))
        return lineREWithThread;

      // Matches old-style Mali perf events
      var lineRENoThread = /^s*()(\w+):\s*([\w\\\/.\-]*):?\s*(.*)$/;
      if (lineRENoThread.test(line))
        return lineRENoThread;
      return null;
    },

    lineRE: null,

    /**
     * Parses maliDDK events and sets up state in the importer.
     * events will come in pairs with a cros_trace_print_enter
     * like this (line broken here for formatting):
     *
     * tracing_mark_write: mali_driver: (mali-012345) cros_trace_print_enter: \
     *   gles/src/texture/mali_gles_texture_slave.c@1505: gles2_texturep_upload
     *
     * and a cros_trace_print_exit like this:
     *
     * tracing_mark_write: mali_driver: (mali-012345) cros_trace_print_exit: \
     *   gles/src/texture/mali_gles_texture_slave.c@1505:
     */
    maliDDKEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      if (this.lineRE == null) {
        this.lineRE = this.autoDetectLineRE(eventBase[2]);
        if (this.lineRE == null)
          return false;
      }
      var maliEvent = this.lineRE.exec(eventBase[2]);
      // Old-style Mali perf events have no thread id, so make one.
      var tid = (maliEvent[1] === '' ? 'mali' : maliEvent[1]);
      switch (maliEvent[2]) {
        case 'cros_trace_print_enter':
          this.maliDDKOpenSlice(pid, tid, ts, maliEvent[4],
              maliEvent[3]);
          break;
        case 'cros_trace_print_exit':
          this.maliDDKCloseSlice(pid, tid, ts, [], maliEvent[3]);
      }
      return true;
    },

    /*
     * Kernel event support.
     */

    dvfsSample: function(counterName, seriesName, ts, value) {
      // NB: record all data on cpu 0; cpuNumber is not meaningful
      var targetCpu = this.importer.getOrCreateCpuState(0);
      var counter = targetCpu.cpu.getOrCreateCounter('', counterName);
      if (counter.numSeries == 0) {
        counter.seriesNames.push(seriesName);
        counter.seriesColors.push(tracing.getStringColorId(counter.name));
      }
      counter.timestamps.push(ts);
      counter.samples.push(value);
    },

    dvfsEventEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /utilization=(\d+)/.exec(eventBase[5]);
      if (!event)
        return false;

      this.dvfsSample('DVFS Utilization', 'utilization', ts, event[1]);
      return true;
    },

    dvfsSetClockEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /frequency=(\d+)/.exec(eventBase[5]);
      if (!event)
        return false;

      this.dvfsSample('DVFS Frequency', 'frequency', ts, event[1]);
      return true;
    },

    dvfsSetVoltageEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /voltage=(\d+)/.exec(eventBase[5]);
      if (!event)
        return false;

      this.dvfsSample('DVFS Voltage', 'voltage', ts, event[1]);
      return true;
    }
  };

  LinuxPerfParser.registerSubtype(LinuxPerfMaliParser);

  return {
    LinuxPerfMaliParser: LinuxPerfMaliParser
  };
});
