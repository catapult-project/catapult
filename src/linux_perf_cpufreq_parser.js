// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * @fileoverview Parses cpufreq events in the Linux event trace format.
 */
base.require('linux_perf_parser');
base.exportTo('tracing', function() {

  var LinuxPerfParser = tracing.LinuxPerfParser;

  /**
   * Parses linux cpufreq trace events.
   * @constructor
   */
  function LinuxPerfCpufreqParser(importer) {
    LinuxPerfParser.call(this, importer);

    importer.registerEventHandler('cpufreq_interactive_up',
        LinuxPerfCpufreqParser.prototype.cpufreqUpDownEvent.bind(this));
    importer.registerEventHandler('cpufreq_interactive_down',
        LinuxPerfCpufreqParser.prototype.cpufreqUpDownEvent.bind(this));
    importer.registerEventHandler('cpufreq_interactive_already',
        LinuxPerfCpufreqParser.prototype.cpufreqTargetEvent.bind(this));
    importer.registerEventHandler('cpufreq_interactive_notyet',
        LinuxPerfCpufreqParser.prototype.cpufreqTargetEvent.bind(this));
    importer.registerEventHandler('cpufreq_interactive_setspeed',
        LinuxPerfCpufreqParser.prototype.cpufreqTargetEvent.bind(this));
    importer.registerEventHandler('cpufreq_interactive_target',
        LinuxPerfCpufreqParser.prototype.cpufreqTargetEvent.bind(this));
    importer.registerEventHandler('cpufreq_interactive_boost',
        LinuxPerfCpufreqParser.prototype.cpufreqBoostUnboostEvent.bind(this));
    importer.registerEventHandler('cpufreq_interactive_unboost',
        LinuxPerfCpufreqParser.prototype.cpufreqBoostUnboostEvent.bind(this));
  }

  function splitData(input) {
    // TODO(sleffler) split by cpu
    var data = {};
    var args = input.split(/\s+/);
    var len = args.length;
    for (var i = 0; i < len; i++) {
      var item = args[i].split('=');
      data[item[0]] = parseInt(item[1]);
    }
    return data;
  }

  LinuxPerfCpufreqParser.prototype = {
    __proto__: LinuxPerfParser.prototype,

    cpufreqSlice: function(ts, eventName, cpu, args) {
      // TODO(sleffler) should be per-cpu
      var kthread = this.importer.getOrCreatePseudoThread('cpufreq');
      kthread.openSlice = eventName;
      var slice = new tracing.TimelineSlice('', kthread.openSlice,
          tracing.getStringColorId(kthread.openSlice), ts, args, 0);

      kthread.thread.pushSlice(slice);
    },

    cpufreqBoostSlice: function(ts, eventName, args) {
      var kthread = this.importer.getOrCreatePseudoThread('cpufreq_boost');
      kthread.openSlice = eventName;
      var slice = new tracing.TimelineSlice('', kthread.openSlice,
          tracing.getStringColorId(kthread.openSlice), ts, args, 0);

      kthread.thread.pushSlice(slice);
    },

    /**
     * Parses cpufreq events and sets up state in the importer.
     */
    cpufreqUpDownEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var data = splitData(eventBase[5]);
      this.cpufreqSlice(ts, eventName, data.cpu, data);
      return true;
    },

    cpufreqTargetEvent: function(eventName, cpuNumber, pid, ts,
                                 eventBase) {
      var data = splitData(eventBase[5]);
      this.cpufreqSlice(ts, eventName, data.cpu, data);
      return true;
    },

    cpufreqBoostUnboostEvent: function(eventName, cpuNumber, pid, ts,
                                       eventBase) {
      this.cpufreqBoostSlice(ts, eventName,
          {
            type: eventBase[5]
          });
      return true;
    }
  };

  LinuxPerfParser.registerSubtype(LinuxPerfCpufreqParser);

  return {
    LinuxPerfCpufreqParser: LinuxPerfCpufreqParser
  };
});
