// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Parses exynos events in the Linux event trace format.
 */
base.require('tracing.importer.linux_perf.parser');
base.exportTo('tracing.importer.linux_perf', function() {

  var Parser = tracing.importer.linux_perf.Parser;

  /**
   * Parses linux exynos trace events.
   * @constructor
   */
  function ExynosParser(importer) {
    Parser.call(this, importer);

    importer.registerEventHandler('exynos_flip_request',
        ExynosParser.prototype.flipEvent.bind(this));
    importer.registerEventHandler('exynos_flip_complete',
        ExynosParser.prototype.flipEvent.bind(this));

    importer.registerEventHandler('exynos_busfreq_target_int',
        ExynosParser.prototype.busfreqTargetIntEvent.bind(this));
    importer.registerEventHandler('exynos_busfreq_target_mif',
        ExynosParser.prototype.busfreqTargetMifEvent.bind(this));
  }

  ExynosParser.prototype = {
    __proto__: Parser.prototype,

    exynosFlipOpenSlice: function(ts, pipe) {
      // use pipe?
      var kthread = this.importer.getOrCreatePseudoThread('exynos_flip');
      kthread.openSliceTS = ts;
      kthread.openSlice = 'flip:' + pipe;
    },

    exynosFlipCloseSlice: function(ts, args) {
      var kthread = this.importer.getOrCreatePseudoThread('exynos_flip');
      if (kthread.openSlice) {
        var slice = new tracing.trace_model.Slice('', kthread.openSlice,
            tracing.getStringColorId(kthread.openSlice),
            kthread.openSliceTS,
            args,
            ts - kthread.openSliceTS);

        kthread.thread.sliceGroup.pushSlice(slice);
      }
      kthread.openSlice = undefined;
    },

    /**
     * Parses exynos events and sets up state in the importer.
     */
    flipEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /pipe=(\d+)/.exec(eventBase.details);
      if (!event)
        return false;

      var pipe = parseInt(event[1]);
      if (eventName == 'exynos_flip_request')
        this.exynosFlipOpenSlice(ts, pipe);
      else
        this.exynosFlipCloseSlice(ts,
            {
              pipe: pipe
            });
      return true;
    },

    exynosBusfreqSample: function(name, ts, frequency) {
      var targetCpu = this.importer.getOrCreateCpuState(0);
      var counter = targetCpu.cpu.getOrCreateCounter('', name);
      if (counter.numSeries === 0) {
        counter.addSeries(new tracing.trace_model.CounterSeries('frequency',
            tracing.getStringColorId(counter.name + '.' + 'frequency')));
      }
      counter.series.forEach(function(series) {
        series.addSample(ts, frequency);
      });
    },

    /**
     * Parses exynos_busfreq_target_int events and sets up state.
     */
    busfreqTargetIntEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /frequency=(\d+)/.exec(eventBase.details);
      if (!event)
        return false;

      this.exynosBusfreqSample('INT Frequency', ts, parseInt(event[1]));
      return true;
    },

    /**
     * Parses exynos_busfreq_target_mif events and sets up state.
     */
    busfreqTargetMifEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /frequency=(\d+)/.exec(eventBase.details);
      if (!event)
        return false;

      this.exynosBusfreqSample('MIF Frequency', ts, parseInt(event[1]));
      return true;
    }
  };

  Parser.registerSubtype(ExynosParser);

  return {
    ExynosParser: ExynosParser
  };
});
