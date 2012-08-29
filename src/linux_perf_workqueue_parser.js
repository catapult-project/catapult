// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * @fileoverview Parses workqueue events in the Linux event trace format.
 */
base.require('linux_perf_parser');
base.exportTo('tracing', function() {

  var LinuxPerfParser = tracing.LinuxPerfParser;

  /**
   * Parses linux workqueue trace events.
   * @constructor
   */
  function LinuxPerfWorkqueueParser(importer) {
    LinuxPerfParser.call(this, importer);

    importer.registerEventHandler('workqueue_execute_start',
        LinuxPerfWorkqueueParser.prototype.executeStartEvent.bind(this));
    importer.registerEventHandler('workqueue_execute_end',
        LinuxPerfWorkqueueParser.prototype.executeEndEvent.bind(this));
  }

  // Matches the workqueue_execute_start record
  //  workqueue_execute_start: work struct c7a8a89c: function MISRWrapper
  var workqueueExecuteStartRE = /work struct (.+): function (\S+)/;

  // Matches the workqueue_execute_start record
  //  workqueue_execute_end: work struct c7a8a89c
  var workqueueExecuteEndRE = /work struct (.+)/;

  LinuxPerfWorkqueueParser.prototype = {
    __proto__: LinuxPerfParser.prototype,

    /**
     * Parses workqueue events and sets up state in the importer.
     */
    executeStartEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = workqueueExecuteStartRE.exec(eventBase[5]);
      if (!event)
        return false;

      var kthread = this.importer.getOrCreateKernelThread(eventBase[1]);
      kthread.openSliceTS = ts;
      kthread.openSlice = event[2];
      return true;
    },

    executeEndEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = workqueueExecuteEndRE.exec(eventBase[5]);
      if (!event)
        return false;

      var kthread = this.importer.getOrCreateKernelThread(eventBase[1]);
      if (kthread.openSlice) {
        var slice = new tracing.TimelineSlice('', kthread.openSlice,
            tracing.getStringColorId(kthread.openSlice),
            kthread.openSliceTS,
            {},
            ts - kthread.openSliceTS);

        kthread.thread.pushSlice(slice);
      }
      kthread.openSlice = undefined;
      return true;
    }
  };

  LinuxPerfParser.registerSubtype(LinuxPerfWorkqueueParser);

  return {
    LinuxPerfWorkqueueParser: LinuxPerfWorkqueueParser
  };
});
