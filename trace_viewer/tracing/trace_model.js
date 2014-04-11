// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview TraceModel is a parsed representation of the
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
tvcm.require('tvcm.range');
tvcm.require('tvcm.events');
tvcm.require('tvcm.interval_tree');
tvcm.require('tracing.importer.importer');
tvcm.require('tracing.importer.task');
tvcm.require('tracing.trace_model.kernel');
tvcm.require('tracing.trace_model.process');
tvcm.require('tracing.trace_model.sample');
tvcm.require('tracing.trace_model.stack_frame');
tvcm.require('tracing.filter');
tvcm.require('tvcm.ui.overlay');

tvcm.exportTo('tracing', function() {

  var Importer = tracing.importer.Importer;
  var Process = tracing.trace_model.Process;
  var Kernel = tracing.trace_model.Kernel;

  /**
   * Builds a model from an array of TraceEvent objects.
   * @param {Object=} opt_eventData Data from a single trace to be imported into
   *     the new model. See TraceModel.importTraces for details on how to
   *     import multiple traces at once.
   * @param {bool=} opt_shiftWorldToZero Whether to shift the world to zero.
   * Defaults to true.
   * @constructor
   */
  function TraceModel(opt_eventData, opt_shiftWorldToZero) {
    this.kernel = new Kernel(this);
    this.processes = {};
    this.metadata = [];
    this.categories = [];
    this.bounds = new tvcm.Range();
    this.instantEvents = [];
    this.flowEvents = [];

    this.stackFrames = {};
    this.samples = [];

    this.flowIntervalTree = new tvcm.IntervalTree(
        function(s) { return s.start; },
        function(e) { return e.start; });

    this.importWarnings_ = [];
    this.reportedImportWarnings_ = {};

    if (opt_eventData)
      this.importTraces([opt_eventData], opt_shiftWorldToZero);
  }

  TraceModel.importerConstructors_ = [];

  /**
   * Registers an importer. All registered importers are considered
   * when processing an import request.
   *
   * @param {Function} importerConstructor The importer's constructor function.
   */
  TraceModel.registerImporter = function(importerConstructor) {
    TraceModel.importerConstructors_.push(importerConstructor);
  };

  TraceModel.prototype = {
    __proto__: tvcm.EventTarget.prototype,

    get numProcesses() {
      var n = 0;
      for (var p in this.processes)
        n++;
      return n;
    },

    /**
     * @return {Process} Gets a TimelineProcess for a specified pid or
     * creates one if it does not exist.
     */
    getOrCreateProcess: function(pid) {
      if (!this.processes[pid])
        this.processes[pid] = new Process(this, pid);
      return this.processes[pid];
    },

    pushInstantEvent: function(instantEvent) {
      this.instantEvents.push(instantEvent);
    },

    addStackFrame: function(stackFrame) {
      if (this.stackFrames[stackFrame.id])
        throw new Error('Stack frame already exists');
      this.stackFrames[stackFrame.id] = stackFrame;
      return stackFrame;
    },

    /**
     * Generates the set of categories from the slices and counters.
     */
    updateCategories_: function() {
      var categoriesDict = {};
      this.kernel.addCategoriesToDict(categoriesDict);
      for (var pid in this.processes)
        this.processes[pid].addCategoriesToDict(categoriesDict);

      this.categories = [];
      for (var category in categoriesDict)
        if (category != '')
          this.categories.push(category);
    },

    updateBounds: function() {
      this.bounds.reset();

      this.kernel.updateBounds();
      this.bounds.addRange(this.kernel.bounds);

      for (var pid in this.processes) {
        this.processes[pid].updateBounds();
        this.bounds.addRange(this.processes[pid].bounds);
      }
    },

    shiftWorldToZero: function() {
      if (this.bounds.isEmpty)
        return;
      var timeBase = this.bounds.min;
      this.kernel.shiftTimestampsForward(-timeBase);

      for (var id in this.instantEvents)
        this.instantEvents[id].start -= timeBase;

      for (var pid in this.processes)
        this.processes[pid].shiftTimestampsForward(-timeBase);

      for (var i = 0; i < this.samples.length; i++) {
        var sample = this.samples[i];
        sample.start -= timeBase;
      }

      this.updateBounds();
    },

    getAllThreads: function() {
      var threads = [];
      for (var tid in this.kernel.threads) {
        threads.push(process.threads[tid]);
      }
      for (var pid in this.processes) {
        var process = this.processes[pid];
        for (var tid in process.threads) {
          threads.push(process.threads[tid]);
        }
      }
      return threads;
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
      counters.push.apply(
          counters, tvcm.dictionaryValues(this.kernel.counters));
      for (var pid in this.processes) {
        var process = this.processes[pid];
        for (var tid in process.counters) {
          counters.push(process.counters[tid]);
        }
      }
      return counters;
    },

    /**
     * @param {String} The name of the thread to find.
     * @return {Array} An array of all the matched threads.
     */
    findAllThreadsNamed: function(name) {
      var namedThreads = [];
      namedThreads.push.apply(
          namedThreads,
          this.kernel.findAllThreadsNamed(name));
      for (var pid in this.processes) {
        namedThreads.push.apply(
            namedThreads,
            this.processes[pid].findAllThreadsNamed(name));
      }
      return namedThreads;
    },

    createImporter_: function(eventData) {
      var importerConstructor;
      for (var i = 0; i < TraceModel.importerConstructors_.length; ++i) {
        if (TraceModel.importerConstructors_[i].canImport(eventData)) {
          importerConstructor = TraceModel.importerConstructors_[i];
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
     * is undefined and will be passed to all the importers registered
     * via TraceModel.registerImporter. The first importer that returns true
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
     * @param {bool=} opt_pruneEmptyContainers Whether to prune empty
     * containers. Defaults to true.
     * @param {Function=} opt_customizeModelCallback Callback called after
     * importers run in which more data can be added to the model, before it is
     * finalized.
     */
    importTraces: function(traces,
                           opt_shiftWorldToZero,
                           opt_pruneEmptyContainers,
                           opt_customizeModelCallback) {
      var progressMeter = {
        update: function(msg) {}
      };
      var task = this.createImportTracesTask(
          progressMeter,
          traces,
          opt_shiftWorldToZero,
          opt_pruneEmptyContainers,
          opt_customizeModelCallback);
      tracing.importer.Task.RunSynchronously(task);
    },

    /**
     * Imports a trace with the usual options from importTraces, but
     * does so using idle callbacks, putting up an import dialog
     * during the import process.
     */
    importTracesWithProgressDialog: function(traces,
                                             opt_shiftWorldToZero,
                                             opt_pruneEmptyContainers,
                                             opt_customizeModelCallback) {
      var overlay = tvcm.ui.Overlay();
      overlay.title = 'Importing...';
      overlay.userCanClose = false;
      overlay.msgEl = document.createElement('div');
      overlay.appendChild(overlay.msgEl);
      overlay.msgEl.style.margin = '20px';
      overlay.update = function(msg) {
        this.msgEl.textContent = msg;
      }
      overlay.visible = true;

      var task = this.createImportTracesTask(
          overlay,
          traces,
          opt_shiftWorldToZero,
          opt_pruneEmptyContainers,
          opt_customizeModelCallback);
      var promise = tracing.importer.Task.RunWhenIdle(task);
      promise.then(
          function() {
            overlay.visible = false;
          }, function(err) {
            overlay.visible = false;
          });
      return promise;
    },

    /**
     * Creates a task that will import the provided traces into the model,
     * updating the progressMeter as it goes. Parameters are as defined in
     * importTraces.
     */
    createImportTracesTask: function(progressMeter,
                                     traces,
                                     opt_shiftWorldToZero,
                                     opt_pruneEmptyContainers,
                                     opt_customizeModelCallback) {
      if (this.importing_)
        throw new Error('Already importing.');
      if (opt_shiftWorldToZero === undefined)
        opt_shiftWorldToZero = true;
      if (opt_pruneEmptyContainers === undefined)
        opt_pruneEmptyContainers = true;
      this.importing_ = true;

      // Just some simple setup. It is useful to have a nop first
      // task so that we can set up the lastTask = lastTask.after()
      // pattern that follows.
      var importTask = new tracing.importer.Task(function() {
        progressMeter.update('I will now import your traces for you...');
      }, this);
      var lastTask = importTask;

      var importers = [];

      lastTask = lastTask.after(function() {
        // Copy the traces array, we may mutate it.
        traces = traces.slice(0);
        progressMeter.update('Creating importers...');
        // Figure out which importers to use.
        for (var i = 0; i < traces.length; ++i)
          importers.push(this.createImporter_(traces[i]));

        // Some traces have other traces inside them. Before doing the full
        // import, ask the importer if it has any subtraces, and if so, create
        // importers for them, also.
        for (var i = 0; i < importers.length; i++) {
          var subtraces = importers[i].extractSubtraces();
          for (var j = 0; j < subtraces.length; j++) {
            traces.push(subtraces[j]);
            importers.push(this.createImporter_(subtraces[j]));
          }
        }

        // Sort them on priority. This ensures importing happens in a
        // predictable order, e.g. linux_perf_importer before
        // trace_event_importer.
        importers.sort(function(x, y) {
          return x.importPriority - y.importPriority;
        });
      }, this);

      // Run the import.
      lastTask = lastTask.after(function(task) {
        importers.forEach(function(importer, index) {
          task.subTask(function() {
            progressMeter.update(
                'Importing ' + (index + 1) + ' of ' + importers.length);
            importer.importEvents(index > 0);
          }, this);
        }, this);
      }, this);

      // Run the cusomizeModelCallback if needed.
      if (opt_customizeModelCallback) {
        lastTask = lastTask.after(function(task) {
          opt_customizeModelCallback(this);
        }, this);
      }

      // Finalize import.
      lastTask = lastTask.after(function(task) {
        importers.forEach(function(importer, index) {
          progressMeter.update(
              'Importing sample data ' + (index + 1) + '/' + importers.length);
          importer.importSampleData();
        }, this);
      }, this);

      // Autoclose open slices and create subSlices.
      lastTask = lastTask.after(function() {
        progressMeter.update('Autoclosing open slices...');
        // Sort the samples.
        this.samples.sort(function(x, y) {
          return x.ts - y.ts;
        });

        this.updateBounds();
        this.kernel.autoCloseOpenSlices(this.bounds.max);
        for (var pid in this.processes)
          this.processes[pid].autoCloseOpenSlices(this.bounds.max);

        this.kernel.createSubSlices();
        for (var pid in this.processes)
          this.processes[pid].createSubSlices();
      }, this);

      // Finalize import.
      lastTask = lastTask.after(function(task) {
        importers.forEach(function(importer, index) {
          progressMeter.update(
              'Finalizing import ' + (index + 1) + '/' + importers.length);
          importer.finalizeImport();
        }, this);
      }, this);

      // Run preinit.
      lastTask = lastTask.after(function() {
        progressMeter.update('Initializing objects (step 1/2)...');
        for (var pid in this.processes)
          this.processes[pid].preInitializeObjects();
      }, this);

      // Prune empty containers.
      if (opt_pruneEmptyContainers) {
        lastTask = lastTask.after(function() {
          progressMeter.update('Pruning empty containers...');
          this.kernel.pruneEmptyContainers();
          for (var pid in this.processes) {
            this.processes[pid].pruneEmptyContainers();
          }
        }, this);
      }

      // Merge kernel and userland slices on each thread.
      lastTask = lastTask.after(function() {
        progressMeter.update('Merging kernel with userland...');
        for (var pid in this.processes)
          this.processes[pid].mergeKernelWithUserland();
      }, this);

      lastTask = lastTask.after(function() {
        progressMeter.update('Computing final world bounds...');
        this.updateBounds();
        this.updateCategories_();

        if (opt_shiftWorldToZero)
          this.shiftWorldToZero();
      }, this);

      // Build the flow event interval tree.
      lastTask = lastTask.after(function() {
        progressMeter.update('Building flow event map...');
        for (var i = 0; i < this.flowEvents.length; ++i) {
          var pair = this.flowEvents[i];
          this.flowIntervalTree.insert(pair[0], pair[1]);
        }
        this.flowIntervalTree.updateHighValues();
      }, this);

      // Join refs.
      lastTask = lastTask.after(function() {
        progressMeter.update('Joining object refs...');
        for (var i = 0; i < importers.length; i++)
          importers[i].joinRefs();
      }, this);

      // Delete any undeleted objects.
      lastTask = lastTask.after(function() {
        progressMeter.update('Cleaning up undeleted objects...');
        for (var pid in this.processes)
          this.processes[pid].autoDeleteObjects(this.bounds.max);
      }, this);

      // Run initializers.
      lastTask = lastTask.after(function() {
        progressMeter.update('Initializing objects (step 2/2)...');
        for (var pid in this.processes)
          this.processes[pid].initializeObjects();
      }, this);

      // Cleanup.
      lastTask.after(function() {
        this.importing_ = false;
      }, this);
      return importTask;
    },

    /**
     * @param {Object} data The import warning data. Data must provide two
     *    accessors: type, message. The types are used to determine if we
     *    should output the message, we'll only output one message of each type.
     *    The message is the actual warning content.
     */
    importWarning: function(data) {
      this.importWarnings_.push(data);

      // Only log each warning type once. We may want to add some kind of
      // flag to allow reporting all importer warnings.
      if (this.reportedImportWarnings_[data.type] === true)
        return;

      console.warn(data.message);
      this.reportedImportWarnings_[data.type] = true;
    },

    get hasImportWarnings() {
      return (this.importWarnings_.length > 0);
    },

    get importWarnings() {
      return this.importWarnings_;
    },

    /**
     * Iterates all events in the model and calls callback on each event.
     * @param {function(event)} callback The callback called for every event.
     */
    iterateAllEvents: function(callback, opt_this) {
      this.instantEvents.forEach(callback, opt_this);

      this.kernel.iterateAllEvents(callback, opt_this);

      for (var pid in this.processes)
        this.processes[pid].iterateAllEvents(callback, opt_this);

      this.samples.forEach(callback, opt_this);
    }
  };

  /**
   * Importer for empty strings and arrays.
   * @constructor
   */
  function TraceModelEmptyImporter(events) {
    this.importPriority = 0;
  };

  TraceModelEmptyImporter.canImport = function(eventData) {
    if (eventData instanceof Array && eventData.length == 0)
      return true;
    if (typeof(eventData) === 'string' || eventData instanceof String) {
      return eventData.length == 0;
    }
    return false;
  };

  TraceModelEmptyImporter.prototype = {
    __proto__: Importer.prototype
  };

  TraceModel.registerImporter(TraceModelEmptyImporter);

  return {
    TraceModel: TraceModel
  };
});
