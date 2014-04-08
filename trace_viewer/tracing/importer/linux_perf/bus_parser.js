// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Parses trace_marker events that were inserted in the trace by
 * userland.
 */
tvcm.require('tracing.importer.linux_perf.parser');
tvcm.require('tracing.trace_model.counter_series');

tvcm.exportTo('tracing.importer.linux_perf', function() {

  var Parser = tracing.importer.linux_perf.Parser;

  /**
   * Parses linux trace mark events that were inserted in the trace by userland.
   * @constructor
   */
  function BusParser(importer) {
    Parser.call(this, importer);

    importer.registerEventHandler('memory_bus_usage',
        BusParser.prototype.traceMarkWriteBusEvent.bind(this));

    this.model_ = importer.model_;
    this.ppids_ = {};
  }

  BusParser.prototype = {
    __proto__: Parser.prototype,

    traceMarkWriteBusEvent: function(eventName, cpuNumber, pid, ts,
                                  eventBase, threadName) {
      var re = new RegExp('bus=(\\S+) rw_bytes=(\\d+) r_bytes=(\\d+) ' +
                            'w_bytes=(\\d+) cycles=(\\d+) ns=(\\d+)');
      var event = re.exec(eventBase.details);

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
      if (ctr.numSeries === 0) {
        ctr.addSeries(new tracing.trace_model.CounterSeries('value',
            tvcm.ui.getStringColorId(ctr.name + '.' + 'value')));
      }
      ctr.series.forEach(function(series) {
        series.addCounterSample(ts, r_bw);
      });

      ctr = this.model_.getOrCreateProcess(0)
              .getOrCreateCounter(null, 'bus ' + name + ' write');
      if (ctr.numSeries === 0) {
        ctr.addSeries(new tracing.trace_model.CounterSeries('value',
            tvcm.ui.getStringColorId(ctr.name + '.' + 'value')));
      }
      ctr.series.forEach(function(series) {
        series.addCounterSample(ts, r_bw);
      });

      return true;
    }
  };

  Parser.registerSubtype(BusParser);

  return {
    BusParser: BusParser
  };
});
