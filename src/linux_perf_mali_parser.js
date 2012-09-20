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

    maliDDKOpenSlice: function(pid, ts, func, blockinfo) {
      var kthread = this.importer.getOrCreateKernelThread('mali_ddk', pid,
                                                          'mali_ddk');
      kthread.thread.beginSlice('gpu-driver', func, ts,
                                { 'blockinfo': blockinfo });
    },

    maliDDKCloseSlice: function(pid, ts, args, blockinfo) {
      var kthread = this.importer.getOrCreateKernelThread('mali_ddk', pid,
                                                          'mali_ddk');
      var thread = kthread.thread;
      if (!thread.openSliceCount) {
        this.importer.importError('maliDDKCloseSlice w/o matching OpenSlice');
        return;
      }
      thread.endSlice(ts);
    },

    /**
     * Parses maliDDK events and sets up state in the importer.
     * events will come in pairs with a cros_trace_print_enter
     * like this:
     *
     * tracing_mark_write: mali_driver: cros_trace_print_enter:
     * gles/src/texture/mali_gles_texture_slave.c1505:
     * gles2_texturep_upload_2d
     *
     * and a cros_trace_print_exit like this:
     *
     * tracing_mark_write: mali_driver: cros_trace_print_exit:
     * gles/src/texture/mali_gles_texture_slave.c1505:
     */
    maliDDKEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var maliEvent =
          /^s*(\w+):\s*([\w\\\/.\-]*):?\s*(.*)$/.exec(eventBase[2]);
      switch (maliEvent[1]) {
        case 'cros_trace_print_enter':
          this.maliDDKOpenSlice(pid, ts, maliEvent[3], maliEvent[2]);
          break;
        case 'cros_trace_print_exit':
          this.maliDDKCloseSlice(pid, ts, [], maliEvent[2]);
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
