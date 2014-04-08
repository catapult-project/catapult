// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Parses exynos events in the Linux event trace format.
 */
tvcm.require('tracing.importer.linux_perf.parser');
tvcm.exportTo('tracing.importer.linux_perf', function() {

  var Parser = tracing.importer.linux_perf.Parser;

  /**
   * Parses linux exynos trace events.
   * @constructor
   */
  function ExynosParser(importer) {
    Parser.call(this, importer);

    importer.registerEventHandler('exynos_busfreq_target_int',
        ExynosParser.prototype.busfreqTargetIntEvent.bind(this));
    importer.registerEventHandler('exynos_busfreq_target_mif',
        ExynosParser.prototype.busfreqTargetMifEvent.bind(this));

    importer.registerEventHandler('exynos_page_flip_state',
        ExynosParser.prototype.pageFlipStateEvent.bind(this));
  }

  ExynosParser.prototype = {
    __proto__: Parser.prototype,

    exynosBusfreqSample: function(name, ts, frequency) {
      var targetCpu = this.importer.getOrCreateCpuState(0);
      var counter = targetCpu.cpu.getOrCreateCounter('', name);
      if (counter.numSeries === 0) {
        counter.addSeries(new tracing.trace_model.CounterSeries('frequency',
            tvcm.ui.getStringColorId(counter.name + '.' + 'frequency')));
      }
      counter.series.forEach(function(series) {
        series.addCounterSample(ts, frequency);
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
    },

    exynosPageFlipStateOpenSlice: function(ts, pipe, fb, state) {
      var kthread = this.importer.getOrCreatePseudoThread(
          'exynos_flip_state (pipe:' + pipe + ', fb:' + fb + ')');
      kthread.openSliceTS = ts;
      kthread.openSlice = state;
    },

    exynosPageFlipStateCloseSlice: function(ts, pipe, fb, args) {
      var kthread = this.importer.getOrCreatePseudoThread(
          'exynos_flip_state (pipe:' + pipe + ', fb:' + fb + ')');
      if (kthread.openSlice) {
        var slice = new tracing.trace_model.Slice('', kthread.openSlice,
            tvcm.ui.getStringColorId(kthread.openSlice),
            kthread.openSliceTS,
            args,
            ts - kthread.openSliceTS);
        kthread.thread.sliceGroup.pushSlice(slice);
      }
      kthread.openSlice = undefined;
    },

    /**
     * Parses page_flip_state events and sets up state in the importer.
     */
    pageFlipStateEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /pipe=(\d+), fb=(\d+), state=(.*)/.exec(eventBase.details);
      if (!event)
        return false;

      var pipe = parseInt(event[1]);
      var fb = parseInt(event[2]);
      var state = event[3];

      this.exynosPageFlipStateCloseSlice(ts, pipe, fb,
          {
            pipe: pipe,
            fb: fb
          });
      if (state !== 'flipped')
        this.exynosPageFlipStateOpenSlice(ts, pipe, fb, state);
      return true;
    }
  };

  Parser.registerSubtype(ExynosParser);

  return {
    ExynosParser: ExynosParser
  };
});
