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
    importer.registerEventHandler('cpufreq_interactive_target',
        LinuxPerfCpufreqParser.prototype.cpufreqTargetEvent.bind(this));
    importer.registerEventHandler('cpufreq_interactive_boost',
        LinuxPerfCpufreqParser.prototype.cpufreqBoostUnboostEvent.bind(this));
    importer.registerEventHandler('cpufreq_interactive_unboost',
        LinuxPerfCpufreqParser.prototype.cpufreqBoostUnboostEvent.bind(this));
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
      var event = /cpu=(\d+) targ=(\d+) actual=(\d+)/.exec(eventBase[5]);
      if (!event)
        return false;

      // TODO(sleffler) split by cpu
      var cpu = parseInt(event[1]);
      var targ = parseInt(event[2]);
      var actual = parseInt(event[3]);
      this.cpufreqSlice(ts, eventName, cpu,
          {
            cpu: cpu,
            targ: targ,
            actual: actual
          });
      return true;
    },

    cpufreqTargetEvent: function(eventName, cpuNumber, pid, ts,
                                 eventBase) {
      var event = /cpu=(\d+) load=(\d+) cur=(\d+) targ=(\d+)/
          .exec(eventBase[5]);
      if (!event)
        return false;

      // TODO(sleffler) split by cpu
      var cpu = parseInt(event[1]);
      var load = parseInt(event[2]);
      var cur = parseInt(event[3]);
      var targ = parseInt(event[4]);
      this.cpufreqSlice(ts, eventName, cpu,
          {
            cpu: cpu,
            load: load,
            cur: cur,
            targ: targ
          });
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
