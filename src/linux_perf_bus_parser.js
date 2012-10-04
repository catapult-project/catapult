// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * @fileoverview Parses trace_marker events that were inserted in the trace by
 * userland.
 */
base.require('linux_perf_parser');
base.exportTo('tracing', function() {

  var LinuxPerfParser = tracing.LinuxPerfParser;

  /**
   * Parses linux trace mark events that were inserted in the trace by userland.
   * @constructor
   */
  function LinuxPerfBusParser(importer) {
    LinuxPerfParser.call(this, importer);

    importer.registerEventHandler('memory_bus_usage',
        LinuxPerfBusParser.prototype.traceMarkWriteBusEvent.bind(this));

    this.model_ = importer.model_;
    this.ppids_ = {};
  }

  LinuxPerfBusParser.prototype = {
    __proto__: LinuxPerfParser.prototype,

    traceMarkWriteBusEvent: function(eventName, cpuNumber, pid, ts,
                                  eventBase, threadName) {
        var re = new RegExp('bus=(\\S+) rw_bytes=(\\d+) r_bytes=(\\d+) ' +
                            'w_bytes=(\\d+) cycles=(\\d+) ns=(\\d+)');
        var event = re.exec(eventBase[5]);

        var name = event[1];
        var rw_bytes = parseInt(event[2]);
        var r_bytes = parseInt(event[3]);
        var w_bytes = parseInt(event[4]);
        var cycles = parseInt(event[5]);
        var ns = parseInt(event[6]);

        // BW in MB/s
        var r_bw = r_bytes * 1000000000 / ns;
        r_bw /= 1024 * 1024;
        var w_bw = w_bytes * 1000000000 / ns;
        w_bw /= 1024 * 1024;

        var ctr = this.model_.getOrCreateProcess(0)
              .getOrCreateCounter(null, 'bus ' + name + ' read');
        // Initialize the counter's series fields if needed.
        if (ctr.numSeries == 0) {
            ctr.seriesNames.push('value');
            ctr.seriesColors.push(
                tracing.getStringColorId(ctr.name + '.' + 'value'));
        }

        // Add the sample value.
        ctr.timestamps.push(ts);
        ctr.samples.push(r_bw);

        ctr = this.model_.getOrCreateProcess(0)
              .getOrCreateCounter(null, 'bus ' + name + ' write');
        // Initialize the counter's series fields if needed.
        if (ctr.numSeries == 0) {
            ctr.seriesNames.push('value');
            ctr.seriesColors.push(
                tracing.getStringColorId(ctr.name + '.' + 'value'));
        }

        // Add the sample value.
        ctr.timestamps.push(ts);
        ctr.samples.push(w_bw);

        return true;
    },
  };

  LinuxPerfParser.registerSubtype(LinuxPerfBusParser);

  return {
    LinuxPerfBusParser: LinuxPerfBusParser
  };
});
