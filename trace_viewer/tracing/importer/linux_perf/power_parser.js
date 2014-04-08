// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Parses power events in the Linux event trace format.
 */
tvcm.require('tracing.importer.linux_perf.parser');
tvcm.require('tracing.trace_model.counter_series');

tvcm.exportTo('tracing.importer.linux_perf', function() {

  var Parser = tracing.importer.linux_perf.Parser;

  /**
   * Parses linux power trace events.
   * @constructor
   */
  function PowerParser(importer) {
    Parser.call(this, importer);

    // NB: old-style power events, deprecated
    importer.registerEventHandler('power_start',
        PowerParser.prototype.powerStartEvent.bind(this));
    importer.registerEventHandler('power_frequency',
        PowerParser.prototype.powerFrequencyEvent.bind(this));

    importer.registerEventHandler('cpu_frequency',
        PowerParser.prototype.cpuFrequencyEvent.bind(this));
    importer.registerEventHandler('cpu_idle',
        PowerParser.prototype.cpuIdleEvent.bind(this));
  }

  PowerParser.prototype = {
    __proto__: Parser.prototype,

    cpuStateSlice: function(ts, targetCpuNumber, eventType, cpuState) {
      var targetCpu = this.importer.getOrCreateCpuState(targetCpuNumber);
      var powerCounter;
      if (eventType != '1') {
        this.importer.model.importWarning({
          type: 'parse_error',
          message: 'Don\'t understand power_start events of ' +
              'type ' + eventType
        });
        return;
      }
      powerCounter = targetCpu.cpu.getOrCreateCounter('', 'C-State');
      if (powerCounter.numSeries === 0) {
        powerCounter.addSeries(new tracing.trace_model.CounterSeries('state',
            tvcm.ui.getStringColorId(powerCounter.name + '.' + 'state')));
      }
      powerCounter.series.forEach(function(series) {
        series.addCounterSample(ts, cpuState);
      });
    },

    cpuIdleSlice: function(ts, targetCpuNumber, cpuState) {
      var targetCpu = this.importer.getOrCreateCpuState(targetCpuNumber);
      var powerCounter = targetCpu.cpu.getOrCreateCounter('', 'C-State');
      if (powerCounter.numSeries === 0) {
        powerCounter.addSeries(new tracing.trace_model.CounterSeries('state',
            tvcm.ui.getStringColorId(powerCounter.name)));
      }
      // NB: 4294967295/-1 means an exit from the current state
      var val = (cpuState != 4294967295 ? cpuState : 0);
      powerCounter.series.forEach(function(series) {
        series.addCounterSample(ts, val);
      });
    },

    cpuFrequencySlice: function(ts, targetCpuNumber, powerState) {
      var targetCpu = this.importer.getOrCreateCpuState(targetCpuNumber);
      var powerCounter =
          targetCpu.cpu.getOrCreateCounter('', 'Clock Frequency');
      if (powerCounter.numSeries === 0) {
        powerCounter.addSeries(new tracing.trace_model.CounterSeries('state',
            tvcm.ui.getStringColorId(powerCounter.name + '.' + 'state')));
      }
      powerCounter.series.forEach(function(series) {
        series.addCounterSample(ts, powerState);
      });
    },

    /**
     * Parses power events and sets up state in the importer.
     */
    powerStartEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /type=(\d+) state=(\d) cpu_id=(\d)+/.exec(eventBase.details);
      if (!event)
        return false;

      var targetCpuNumber = parseInt(event[3]);
      var cpuState = parseInt(event[2]);
      this.cpuStateSlice(ts, targetCpuNumber, event[1], cpuState);
      return true;
    },

    powerFrequencyEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /type=(\d+) state=(\d+) cpu_id=(\d)+/
          .exec(eventBase.details);
      if (!event)
        return false;

      var targetCpuNumber = parseInt(event[3]);
      var powerState = parseInt(event[2]);
      this.cpuFrequencySlice(ts, targetCpuNumber, powerState);
      return true;
    },

    cpuFrequencyEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /state=(\d+) cpu_id=(\d)+/.exec(eventBase.details);
      if (!event)
        return false;

      var targetCpuNumber = parseInt(event[2]);
      var powerState = parseInt(event[1]);
      this.cpuFrequencySlice(ts, targetCpuNumber, powerState);
      return true;
    },

    cpuIdleEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /state=(\d+) cpu_id=(\d)+/.exec(eventBase.details);
      if (!event)
        return false;

      var targetCpuNumber = parseInt(event[2]);
      var cpuState = parseInt(event[1]);
      this.cpuIdleSlice(ts, targetCpuNumber, cpuState);
      return true;
    }
  };

  Parser.registerSubtype(PowerParser);

  return {
    PowerParser: PowerParser
  };
});
