// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview TimelineModel is a parsed representation of the
 * TraceEvents obtained from base/trace_event in which the begin-end
 * tokens are converted into a hierarchy of processes, threads,
 * subrows, and slices.
 *
 * The building block of the model is a slice. A slice is roughly
 * equivalent to function call executing on a specific thread. As a
 * result, slices may have one or more subslices.
 *
 * A thread contains one or more subrows of slices. Row 0 corresponds to
 * the "root" slices, e.g. the topmost slices. Row 1 contains slices that
 * are nested 1 deep in the stack, and so on. We use these subrows to draw
 * nesting tasks.
 *
 */
base.defineModule('timeline_model')
    .dependsOn('event_target',
               'timeline_process',
               'timeline_cpu')
    .exportsTo('tracing', function() {

  var TimelineProcess = tracing.TimelineProcess;
  var TimelineCpu = tracing.TimelineCpu;

  /**
   * Builds a model from an array of TraceEvent objects.
   * @param {Object=} opt_data The event data to import into the new model.
   *     See TimelineModel.importEvents for details and more advanced ways to
   *     import data.
   * @param {bool=} opt_zeroAndBoost Whether to align to zero and boost the
   *     by 15%. Defaults to true.
   * @constructor
   */
  function TimelineModel(opt_eventData, opt_zeroAndBoost) {
    this.cpus = {};
    this.processes = {};
    this.importErrors = [];
    this.asyncSliceGroups = {};

    if (opt_eventData)
      this.importEvents(opt_eventData, opt_zeroAndBoost);
  }

  var importerConstructors = [];

  /**
   * Registers an importer. All registered importers are considered
   * when processing an import request.
   *
   * @param {Function} importerConstructor The importer's constructor function.
   */
  TimelineModel.registerImporter = function(importerConstructor) {
    importerConstructors.push(importerConstructor);
  };

  function TimelineModelEmptyImporter(events) {
  };

  TimelineModelEmptyImporter.canImport = function(eventData) {
    if (eventData instanceof Array && eventData.length == 0)
      return true;
    if (typeof(eventData) === 'string' || eventData instanceof String) {
      return eventData.length == 0;
    }
    return false;
  };

  TimelineModelEmptyImporter.prototype = {
    __proto__: Object.prototype,

    importEvents: function() {
    },
    finalizeImport: function() {
    }
  };

  TimelineModel.registerImporter(TimelineModelEmptyImporter);

  TimelineModel.prototype = {
    __proto__: base.EventTarget.prototype,

    get numProcesses() {
      var n = 0;
      for (var p in this.processes)
        n++;
      return n;
    },

    /**
     * @return {TimelineProcess} Gets a specific TimelineCpu or creates one if
     * it does not exist.
     */
    getOrCreateCpu: function(cpuNumber) {
      if (!this.cpus[cpuNumber])
        this.cpus[cpuNumber] = new TimelineCpu(cpuNumber);
      return this.cpus[cpuNumber];
    },

    /**
     * @return {TimelineProcess} Gets a TimlineProcess for a specified pid or
     * creates one if it does not exist.
     */
    getOrCreateProcess: function(pid) {
      if (!this.processes[pid])
        this.processes[pid] = new TimelineProcess(pid);
      return this.processes[pid];
    },

    /**
     * The import takes an array of json-ified TraceEvents and adds them into
     * the TimelineModel as processes, threads, and slices.
     */

    /**
     * Removes threads from the model that are fully empty.
     */
    pruneEmptyThreads: function() {
      for (var pid in this.processes) {
        var process = this.processes[pid];
        var prunedThreads = {};
        for (var tid in process.threads) {
          var thread = process.threads[tid];

          // Begin-events without matching end events leave a thread in a state
          // where the toplevel subrows are empty but child subrows have
          // entries. The autocloser will fix this up later. But, for the
          // purposes of pruning, such threads need to be treated as having
          // content.
          var hasNonEmptySubrow = false;
          for (var s = 0; s < thread.subRows.length; s++)
            hasNonEmptySubrow |= thread.subRows[s].length > 0;

          if (hasNonEmptySubrow || thread.asyncSlices.length > 0)
            prunedThreads[tid] = thread;
        }
        process.threads = prunedThreads;
      }
    },

    updateBounds: function() {
      var wmin = Infinity;
      var wmax = -wmin;
      var hasData = false;

      var threads = this.getAllThreads();
      for (var tI = 0; tI < threads.length; tI++) {
        var thread = threads[tI];
        thread.updateBounds();
        if (thread.minTimestamp != undefined &&
            thread.maxTimestamp != undefined) {
          wmin = Math.min(wmin, thread.minTimestamp);
          wmax = Math.max(wmax, thread.maxTimestamp);
          hasData = true;
        }
      }
      var counters = this.getAllCounters();
      for (var tI = 0; tI < counters.length; tI++) {
        var counter = counters[tI];
        counter.updateBounds();
        if (counter.minTimestamp != undefined &&
            counter.maxTimestamp != undefined) {
          hasData = true;
          wmin = Math.min(wmin, counter.minTimestamp);
          wmax = Math.max(wmax, counter.maxTimestamp);
        }
      }

      for (var cpuNumber in this.cpus) {
        var cpu = this.cpus[cpuNumber];
        cpu.updateBounds();
        if (cpu.minTimestamp != undefined &&
            cpu.maxTimestamp != undefined) {
          hasData = true;
          wmin = Math.min(wmin, cpu.minTimestamp);
          wmax = Math.max(wmax, cpu.maxTimestamp);
        }
      }

      if (hasData) {
        this.minTimestamp = wmin;
        this.maxTimestamp = wmax;
      } else {
        this.maxTimestamp = undefined;
        this.minTimestamp = undefined;
      }
    },

    shiftWorldToZero: function() {
      if (this.minTimestamp === undefined)
        return;
      var timeBase = this.minTimestamp;
      for (var pid in this.processes)
        this.processes[pid].shiftTimestampsForward(-timeBase);
      for (var cpuNumber in this.cpus)
        this.cpus[cpuNumber].shiftTimestampsForward(-timeBase);
      this.updateBounds();
    },

    getAllThreads: function() {
      var threads = [];
      for (var pid in this.processes) {
        var process = this.processes[pid];
        for (var tid in process.threads) {
          threads.push(process.threads[tid]);
        }
      }
      return threads;
    },

    /**
     * @return {Array} An array of all cpus in the model.
     */
    getAllCpus: function() {
      var cpus = [];
      for (var cpu in this.cpus)
        cpus.push(this.cpus[cpu]);
      return cpus;
    },

    /**
     * @return {Array} An array of all processes in the model.
     */
    getAllProcesses: function() {
      var processes = [];
      for (var pid in this.processes)
        processes.push(this.processes[pid]);
      return processes;
    },

    /**
     * @return {Array} An array of all the counters in the model.
     */
    getAllCounters: function() {
      var counters = [];
      for (var pid in this.processes) {
        var process = this.processes[pid];
        for (var tid in process.counters) {
          counters.push(process.counters[tid]);
        }
      }
      for (var cpuNumber in this.cpus) {
        var cpu = this.cpus[cpuNumber];
        for (var counterName in cpu.counters)
          counters.push(cpu.counters[counterName]);
      }
      return counters;
    },

    /**
     * Imports the provided events into the model. The eventData type
     * is undefined and will be passed to all the timeline importers registered
     * via TimelineModel.registerImporter. The first importer that returns true
     * for canImport(events) will be used to import the events.
     *
     * @param {Object} events Events to import.
     * @param {boolean} isAdditionalImport True the eventData being imported is
     *     an additional trace after the primary eventData.
     * @return {TimelineModelImporter} The importer used for the eventData.
     */
    importOneTrace_: function(eventData, isAdditionalImport) {
      var importerConstructor;
      for (var i = 0; i < importerConstructors.length; ++i) {
        if (importerConstructors[i].canImport(eventData)) {
          importerConstructor = importerConstructors[i];
          break;
        }
      }
      if (!importerConstructor)
        throw new Error(
            'Could not find an importer for the provided eventData.');

      var importer = new importerConstructor(
          this, eventData, isAdditionalImport);
      importer.importEvents();
      return importer;
    },

    /**
     * Imports the provided traces into the model. The eventData type
     * is undefined and will be passed to all the timeline importers registered
     * via TimelineModel.registerImporter. The first importer that returns true
     * for canImport(events) will be used to import the events.
     *
     * The primary trace is provided via the eventData variable. If multiple
     * traces are to be imported, specify the first one as events, and the
     * remainder in the opt_additionalEventData array.
     *
     * @param {Object} eventData Events to import.
     * @param {bool=} opt_zeroAndBoost Whether to align to zero and boost the
     *     by 15%. Defaults to true.
     * @param {Array=} opt_additionalEventData An array of eventData objects
     *     (e.g. array of arrays) to
     * import after importing the primary events.
     */
    importEvents: function(eventData,
                           opt_zeroAndBoost, opt_additionalEventData) {
      if (opt_zeroAndBoost === undefined)
        opt_zeroAndBoost = true;

      var activeImporters = [];
      var importer = this.importOneTrace_(eventData, false);
      activeImporters.push(importer);
      if (opt_additionalEventData) {
        for (var i = 0; i < opt_additionalEventData.length; ++i) {
          importer = this.importOneTrace_(opt_additionalEventData[i], true);
          activeImporters.push(importer);
        }
      }
      for (var i = 0; i < activeImporters.length; ++i)
        activeImporters[i].finalizeImport();

      for (var i = 0; i < activeImporters.length; ++i)
        this.pruneEmptyThreads();

      this.updateBounds();

      if (opt_zeroAndBoost)
        this.shiftWorldToZero();

      if (opt_zeroAndBoost &&
          this.minTimestamp !== undefined &&
          this.maxTimestamp !== undefined) {
        var boost = (this.maxTimestamp - this.minTimestamp) * 0.15;
        this.minTimestamp = this.minTimestamp - boost;
        this.maxTimestamp = this.maxTimestamp + boost;
      }
    }
  };

  /**
   * @constructor A filter that can be passed into
   * Timeline.findAllObjectsMatchingFilter
   */
  function TimelineFilter(text) {
    this.text_ = text;
  }
  TimelineFilter.prototype = {
    __proto__: Object.prototype,

    matchSlice: function(slice) {
      if (this.text_.length == 0)
        return false;
      return slice.title.indexOf(this.text_) != -1;
    }

  };

  return {
    TimelineModel: TimelineModel,
    TimelineFilter: TimelineFilter
  };

});
