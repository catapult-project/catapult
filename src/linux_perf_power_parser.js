// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * @fileoverview Parses power events in the Linux event trace format.
 */
base.require('linux_perf_parser');
base.exportTo('tracing', function() {

  var LinuxPerfParser = tracing.LinuxPerfParser;

  /**
   * Parses linux power trace events.
   * @constructor
   */
  function LinuxPerfPowerParser(importer) {
    LinuxPerfParser.call(this, importer);

    // NB: old-style power events, deprecated
    importer.registerEventHandler('power_start',
        LinuxPerfPowerParser.prototype.powerStartEvent.bind(this));
    importer.registerEventHandler('power_frequency',
        LinuxPerfPowerParser.prototype.powerFrequencyEvent.bind(this));

    importer.registerEventHandler('cpu_frequency',
        LinuxPerfPowerParser.prototype.cpuFrequencyEvent.bind(this));
    importer.registerEventHandler('cpu_idle',
        LinuxPerfPowerParser.prototype.cpuIdleEvent.bind(this));
  }

  LinuxPerfPowerParser.prototype = {
    __proto__: LinuxPerfParser.prototype,

    cpuStateSlice: function(ts, targetCpuNumber, eventType, cpuState) {
      var targetCpu = this.importer.getOrCreateCpuState(targetCpuNumber);
      var powerCounter;
      if (eventType != '1') {
        this.importer.importError('Don\'t understand power_start events of ' +
            'type ' + eventType);
        return;
      }
      powerCounter = targetCpu.cpu.getOrCreateCounter('', 'C-State');
      if (powerCounter.numSeries == 0) {
        powerCounter.seriesNames.push('state');
        powerCounter.seriesColors.push(
            tracing.getStringColorId(powerCounter.name + '.' + 'state'));
      }
      powerCounter.timestamps.push(ts);
      powerCounter.samples.push(cpuState);
    },

    cpuIdleSlice: function(ts, targetCpuNumber, cpuState) {
      var targetCpu = this.importer.getOrCreateCpuState(targetCpuNumber);
      var powerCounter = targetCpu.cpu.getOrCreateCounter('', 'C-State');
      if (powerCounter.numSeries == 0) {
        powerCounter.seriesNames.push('state');
        powerCounter.seriesColors.push(
            tracing.getStringColorId(powerCounter.name));
      }
      // NB: 4294967295/-1 means an exit from the current state
      if (cpuState != 4294967295)
        powerCounter.samples.push(cpuState);
      else
        powerCounter.samples.push(0);
      powerCounter.timestamps.push(ts);
    },

    cpuFrequencySlice: function(ts, targetCpuNumber, powerState) {
      var targetCpu = this.importer.getOrCreateCpuState(targetCpuNumber);
      var powerCounter =
          targetCpu.cpu.getOrCreateCounter('', 'Clock Frequency');
      if (powerCounter.numSeries == 0) {
        powerCounter.seriesNames.push('state');
        powerCounter.seriesColors.push(
            tracing.getStringColorId(powerCounter.name + '.' + 'state'));
      }
      powerCounter.timestamps.push(ts);
      powerCounter.samples.push(powerState);
    },

    /**
     * Parses power events and sets up state in the importer.
     */
    powerStartEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /type=(\d+) state=(\d) cpu_id=(\d)+/.exec(eventBase[5]);
      if (!event)
        return false;

      var targetCpuNumber = parseInt(event[3]);
      var cpuState = parseInt(event[2]);
      this.cpuStateSlice(ts, targetCpuNumber, event[1], cpuState);
      return true;
    },

    powerFrequencyEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /type=(\d+) state=(\d+) cpu_id=(\d)+/
          .exec(eventBase[5]);
      if (!event)
        return false;

      var targetCpuNumber = parseInt(event[3]);
      var powerState = parseInt(event[2]);
      this.cpuFrequencySlice(ts, targetCpuNumber, powerState);
      return true;
    },

    cpuFrequencyEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /state=(\d+) cpu_id=(\d)+/.exec(eventBase[5]);
      if (!event)
        return false;

      var targetCpuNumber = parseInt(event[2]);
      var powerState = parseInt(event[1]);
      this.cpuFrequencySlice(ts, targetCpuNumber, powerState);
      return true;
    },

    cpuIdleEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /state=(\d+) cpu_id=(\d)+/.exec(eventBase[5]);
      if (!event)
        return false;

      var targetCpuNumber = parseInt(event[2]);
      var cpuState = parseInt(event[1]);
      this.cpuIdleSlice(ts, targetCpuNumber, cpuState);
      return true;
    }
  };

  LinuxPerfParser.registerSubtype(LinuxPerfPowerParser);

  return {
    LinuxPerfPowerParser: LinuxPerfPowerParser
  };
});
