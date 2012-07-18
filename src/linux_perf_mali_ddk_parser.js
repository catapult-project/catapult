// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * @fileoverview Parses Mali DDK events in the Linux event trace format.
 */
base.defineModule('linux_perf_mali_ddk_parser')
  .dependsOn('linux_perf_parser')
  .exportsTo('tracing', function() {

  var LinuxPerfParser = tracing.LinuxPerfParser;

  /**
   * Parses Mali DDK trace events.
   * @constructor
   */
  function LinuxPerfMaliDDKParser(importer) {
    LinuxPerfParser.call(this, importer);
    importer.registerEventHandler('tracing_mark_write:mali_driver',
        LinuxPerfMaliDDKParser.prototype.maliDDKEvent.bind(this));
  }

  LinuxPerfMaliDDKParser.prototype = {
    __proto__: LinuxPerfParser.prototype,

    maliDDKOpenSlice: function(pid, ts, func, blockinfo) {
      var kthread = this.importer.getOrCreateKernelThread('mali_ddk', pid,
                                                          'mali_ddk');
      kthread.thread.beginSlice(func, ts, { 'blockinfo':blockinfo });
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
    }
  };

  LinuxPerfParser.registerSubtype(LinuxPerfMaliDDKParser);

  return {
    LinuxPerfMaliDDKParser: LinuxPerfMaliDDKParser
  };
});
