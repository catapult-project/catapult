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
base.require('event_target');
base.require('timeline_process');
base.require('timeline_cpu');
base.require('timeline_filter');
base.exportTo('tracing', function() {

  var TimelineProcess = tracing.TimelineProcess;
  var TimelineCpu = tracing.TimelineCpu;

  /**
   * Builds a model from an array of TraceEvent objects.
   * @param {Object=} opt_eventData Data from a single trace to be imported into
   *     the new model. See TimelineModel.importTraces for details on how to
   *     import multiple traces at once.
   * @param {bool=} opt_shiftWorldToZero Whether to shift the world to zero.
   * Defaults to true.
   * @constructor
   */
  function TimelineModel(opt_eventData, opt_shiftWorldToZero) {
    this.cpus = {};
    this.processes = {};
    this.importErrors = [];
    this.metadata = [];
    this.categories = [];

    if (opt_eventData)
      this.importTraces([opt_eventData], opt_shiftWorldToZero);
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
    this.importPriority = 0;
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
     * Closes any slices that need closing
     */
    autoCloseOpenSlices_: function() {
      this.updateBounds();
      var maxTimestamp = this.maxTimestamp;
      for (var pid in this.processes) {
        var process = this.processes[pid];
        for (var tid in process.threads) {
          var thread = process.threads[tid];
          thread.autoCloseOpenSlices(maxTimestamp);
        }
      }
    },

    /**
     * Generates the set of categories from the slices.
     */
    updateCategories_: function() {
      // TODO(sullivan): Is there a way to do this more cleanly?
      for (var pid in this.processes) {
        var process = this.processes[pid];
        for (var tid in process.threads) {
          var slices = process.threads[tid].slices;
          for (var i = 0; i < slices.length; i++) {
            var category = slices[i].category;
            if (category && this.categories.indexOf(category) == -1) {
              this.categories.push(category);
            }
          }
        }
      }
      for (var cpu in this.cpus) {
        var slices = this.cpus[cpu].slices;
        for (var i = 0; i < slices.length; i++) {
          var category = slices[i].category;
          if (category && this.categories.indexOf(category) == -1) {
            this.categories.push(category);
          }
        }
      }
    },

    /**
     * Removes threads from the model that are fully empty.
     */
    pruneEmptyThreads_: function() {
      for (var pid in this.processes) {
        var process = this.processes[pid];
        var threadsToKeep = {};
        for (var tid in process.threads) {
          var thread = process.threads[tid];
          if (!thread.isEmpty)
            threadsToKeep[tid] = thread;
        }
        process.threads = threadsToKeep;
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
     * @param {String} The name of the thread to find.
     * @return {Array} An array of all the matched threads.
     */
    findAllThreadsNamed: function(name) {
      var namedThreads = [];
      var threads = this.getAllThreads();
      for (var i = 0; i < threads.length; i++) {
        var thread = threads[i];
        if (thread.name == name)
          namedThreads.push(thread);
      }
      return namedThreads;
    },

    createImporter_: function(eventData) {
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
          this, eventData);
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
     * @param {Array} traces An array of eventData to be imported. Each
     * eventData should correspond to a single trace file and will be handled by
     * a separate importer.
     * @param {bool=} opt_shiftWorldToZero Whether to shift the world to zero.
     * Defaults to true.
     */
    importTraces: function(traces,
                           opt_shiftWorldToZero) {
      if (opt_shiftWorldToZero === undefined)
        opt_shiftWorldToZero = true;

      // Figure out which importers to use.
      var importers = [];
      for (var i = 0; i < traces.length; ++i)
        importers.push(this.createImporter_(traces[i]));

      // Sort them on priority. This ensures importing happens in a predictable
      // order, e.g. linux_perf_importer before trace_event_importer.
      importers.sort(function(x, y) {
        return x.importPriority - y.importPriority;
      });

      // Run the import.
      for (var i = 0; i < importers.length; i++)
        importers[i].importEvents(i > 0);

      this.autoCloseOpenSlices_();

      for (var i = 0; i < importers.length; i++)
        importers[i].finalizeImport();

      this.pruneEmptyThreads_();
      this.updateBounds();

      this.updateCategories_();

      if (opt_shiftWorldToZero)
        this.shiftWorldToZero();
    }
  };

  return {
    TimelineModel: TimelineModel
  };

});
