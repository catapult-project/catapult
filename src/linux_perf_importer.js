// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * @fileoverview Imports text files in the Linux event trace format into the
 * timeline model. This format is output both by sched_trace and by Linux's perf
 * tool.
 *
 * This importer assumes the events arrive as a string. The unit tests provide
 * examples of the trace format.
 *
 * Linux scheduler traces use a definition for 'pid' that is different than
 * tracing uses. Whereas tracing uses pid to identify a specific process, a pid
 * in a linux trace refers to a specific thread within a process. Within this
 * file, we the definition used in Linux traces, as it improves the importing
 * code's readability.
 */
base.require('timeline_model');
base.require('timeline_color_scheme');
base.require('linux_perf_bus_parser');
base.require('linux_perf_clock_parser');
base.require('linux_perf_cpufreq_parser');
base.require('linux_perf_drm_parser');
base.require('linux_perf_exynos_parser');
base.require('linux_perf_gesture_parser');
base.require('linux_perf_i915_parser');
base.require('linux_perf_mali_parser');
base.require('linux_perf_power_parser');
base.require('linux_perf_sched_parser');
base.require('linux_perf_workqueue_parser');
base.require('linux_perf_android_parser');

base.exportTo('tracing', function() {
  /**
   * Represents the scheduling state for a single thread.
   * @constructor
   */
  function CpuState(cpu) {
    this.cpu = cpu;
  }

  CpuState.prototype = {
    __proto__: Object.prototype,

    /**
     * Switches the active pid on this Cpu. If necessary, add a TimelineSlice
     * to the cpu representing the time spent on that Cpu since the last call to
     * switchRunningLinuxPid.
     */
    switchRunningLinuxPid: function(importer, prevState, ts, pid, comm, prio) {
      // Generate a slice if the last active pid was not the idle task
      if (this.lastActivePid !== undefined && this.lastActivePid != 0) {
        var duration = ts - this.lastActiveTs;
        var thread = importer.threadsByLinuxPid[this.lastActivePid];
        if (thread)
          name = thread.userFriendlyName;
        else
          name = this.lastActiveComm;

        var slice = new tracing.TimelineSlice('', name,
                                              tracing.getStringColorId(name),
                                              this.lastActiveTs,
                                              {
                                                comm: this.lastActiveComm,
                                                tid: this.lastActivePid,
                                                prio: this.lastActivePrio,
                                                stateWhenDescheduled: prevState
                                              },
                                              duration);
        this.cpu.slices.push(slice);
      }

      this.lastActiveTs = ts;
      this.lastActivePid = pid;
      this.lastActiveComm = comm;
      this.lastActivePrio = prio;
    }
  };

  /**
   * Imports linux perf events into a specified model.
   * @constructor
   */
  function LinuxPerfImporter(model, events) {
    this.importPriority = 2;
    this.model_ = model;
    this.events_ = events;
    this.clockSyncRecords_ = [];
    this.cpuStates_ = {};
    this.kernelThreadStates_ = {};
    this.buildMapFromLinuxPidsToTimelineThreads();
    this.lineNumber = -1;
    this.pseudoThreadCounter = 1;
    this.parsers_ = [];
    this.eventHandlers_ = {};
  }

  TestExports = {};

  // Matches the default trace record in 3.2 and later (includes irq-info):
  //          <idle>-0     [001] d...  1.23: sched_switch
  var lineREWithIRQInfo = new RegExp(
      '^\\s*(.+?)\\s+\\[(\\d+)\\]' + '\\s+[dX.][N.][Hhs.][0-9a-f.]' +
      '\\s+(\\d+\\.\\d+):\\s+(\\S+):\\s(.*)$');
  TestExports.lineREWithIRQInfo = lineREWithIRQInfo;

  // Matches the default trace record pre-3.2:
  //          <idle>-0     [001]  1.23: sched_switch
  var lineRE = /^\s*(.+?)\s+\[(\d+)\]\s*(\d+\.\d+):\s+(\S+):\s(.*)$/;
  TestExports.lineRE = lineRE;

  // Matches the trace_event_clock_sync record
  //  0: trace_event_clock_sync: parent_ts=19581477508
  var traceEventClockSyncRE = /trace_event_clock_sync: parent_ts=(\d+\.?\d*)/;
  TestExports.traceEventClockSyncRE = traceEventClockSyncRE;

  // Some kernel trace events are manually classified in slices and
  // hand-assigned a pseudo PID.
  var pseudoKernelPID = 0;

  /**
   * Deduce the format of trace data. Linix kernels prior to 3.3 used
   * one format (by default); 3.4 and later used another.
   *
   * @return {string} the regular expression for parsing data when
   * the format is recognized; otherwise null.
   */
  function autoDetectLineRE(line) {
    if (lineREWithIRQInfo.test(line))
      return lineREWithIRQInfo;
    if (lineRE.test(line))
      return lineRE;
    return null;
  };
  TestExports.autoDetectLineRE = autoDetectLineRE;

  /**
   * Guesses whether the provided events is a Linux perf string.
   * Looks for the magic string "# tracer" at the start of the file,
   * or the typical task-pid-cpu-timestamp-function sequence of a typical
   * trace's body.
   *
   * @return {boolean} True when events is a linux perf array.
   */
  LinuxPerfImporter.canImport = function(events) {
    if (!(typeof(events) === 'string' || events instanceof String))
      return false;

    if (/^# tracer:/.test(events))
      return true;

    var m = /^(.+)\n/.exec(events);
    if (m)
      events = m[1];
    if (autoDetectLineRE(events))
      return true;

    return false;
  };

  LinuxPerfImporter.prototype = {
    __proto__: Object.prototype,

    /**
     * Precomputes a lookup table from linux pids back to existing
     * TimelineThreads. This is used during importing to add information to each
     * timeline thread about whether it was running, descheduled, sleeping, et
     * cetera.
     */
    buildMapFromLinuxPidsToTimelineThreads: function() {
      this.threadsByLinuxPid = {};
      this.model_.getAllThreads().forEach(
          function(thread) {
            this.threadsByLinuxPid[thread.tid] = thread;
          }.bind(this));
    },

    /**
     * @return {CpuState} A CpuState corresponding to the given cpuNumber.
     */
    getOrCreateCpuState: function(cpuNumber) {
      if (!this.cpuStates_[cpuNumber]) {
        var cpu = this.model_.getOrCreateCpu(cpuNumber);
        this.cpuStates_[cpuNumber] = new CpuState(cpu);
      }
      return this.cpuStates_[cpuNumber];
    },

    /**
     * @return {TimelinThread} A thread corresponding to the kernelThreadName.
     */
    getOrCreateKernelThread: function(kernelThreadName, opt_pid, opt_tid) {
      if (!this.kernelThreadStates_[kernelThreadName]) {
        var pid = opt_pid;
        if (pid == undefined) {
          pid = /.+-(\d+)/.exec(kernelThreadName)[1];
          pid = parseInt(pid, 10);
        }
        var tid = opt_tid;
        if (tid == undefined)
          tid = pid;

        var thread = this.model_.getOrCreateProcess(pid).getOrCreateThread(tid);
        thread.name = kernelThreadName;
        this.kernelThreadStates_[kernelThreadName] = {
          pid: pid,
          thread: thread,
          openSlice: undefined,
          openSliceTS: undefined
        };
        this.threadsByLinuxPid[pid] = thread;
      }
      return this.kernelThreadStates_[kernelThreadName];
    },

    /**
     * @return {TimelinThread} A pseudo thread corresponding to the
     * threadName.  Pseudo threads are for events that we want to break
     * out to a separate timeline but would not otherwise happen.
     * These threads are assigned to pseudoKernelPID and given a
     * unique (incrementing) TID.
     */
    getOrCreatePseudoThread: function(threadName) {
      var thread = this.kernelThreadStates_[threadName];
      if (!thread) {
        thread = this.getOrCreateKernelThread(threadName, pseudoKernelPID,
            this.pseudoThreadCounter);
        this.pseudoThreadCounter++;
      }
      return thread;
    },

    /**
     * Imports the data in this.events_ into model_.
     */
    importEvents: function(isSecondaryImport) {
      this.createParsers();
      this.importCpuData();
      if (!this.alignClocks(isSecondaryImport))
        return;
      this.buildMapFromLinuxPidsToTimelineThreads();
      this.buildPerThreadCpuSlicesFromCpuState();
    },

    /**
     * Called by the TimelineModel after all other importers have imported their
     * events.
     */
    finalizeImport: function() {
    },

    /**
     * Builds the cpuSlices array on each thread based on our knowledge of what
     * each Cpu is doing.  This is done only for TimelineThreads that are
     * already in the model, on the assumption that not having any traced data
     * on a thread means that it is not of interest to the user.
     */
    buildPerThreadCpuSlicesFromCpuState: function() {
      // Push the cpu slices to the threads that they run on.
      for (var cpuNumber in this.cpuStates_) {
        var cpuState = this.cpuStates_[cpuNumber];
        var cpu = cpuState.cpu;

        for (var i = 0; i < cpu.slices.length; i++) {
          var slice = cpu.slices[i];

          var thread = this.threadsByLinuxPid[slice.args.tid];
          if (!thread)
            continue;
          if (!thread.tempCpuSlices)
            thread.tempCpuSlices = [];
          thread.tempCpuSlices.push(slice);
        }
      }

      // Create slices for when the thread is not running.
      var runningId = tracing.getColorIdByName('running');
      var runnableId = tracing.getColorIdByName('runnable');
      var sleepingId = tracing.getColorIdByName('sleeping');
      var ioWaitId = tracing.getColorIdByName('iowait');
      this.model_.getAllThreads().forEach(function(thread) {
        if (!thread.tempCpuSlices)
          return;
        var origSlices = thread.tempCpuSlices;
        delete thread.tempCpuSlices;

        origSlices.sort(function(x, y) {
          return x.start - y.start;
        });

        // Walk the slice list and put slices between each original slice
        // to show when the thread isn't running
        var slices = [];
        if (origSlices.length) {
          var slice = origSlices[0];
          slices.push(new tracing.TimelineSlice('', 'Running', runningId,
              slice.start, {}, slice.duration));
        }
        for (var i = 1; i < origSlices.length; i++) {
          var prevSlice = origSlices[i - 1];
          var nextSlice = origSlices[i];
          var midDuration = nextSlice.start - prevSlice.end;
          if (prevSlice.args.stateWhenDescheduled == 'S') {
            slices.push(new tracing.TimelineSlice('', 'Sleeping', sleepingId,
                prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 'R' ||
                     prevSlice.args.stateWhenDescheduled == 'R+') {
            slices.push(new tracing.TimelineSlice('', 'Runnable', runnableId,
                prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 'D') {
            slices.push(new tracing.TimelineSlice(
                '', 'Uninterruptible Sleep', ioWaitId,
                prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 'T') {
            slices.push(new tracing.TimelineSlice('', '__TASK_STOPPED',
                ioWaitId, prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 't') {
            slices.push(new tracing.TimelineSlice('', 'debug', ioWaitId,
                prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 'Z') {
            slices.push(new tracing.TimelineSlice('', 'Zombie', ioWaitId,
                prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 'X') {
            slices.push(new tracing.TimelineSlice('', 'Exit Dead', ioWaitId,
                prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 'x') {
            slices.push(new tracing.TimelineSlice('', 'Task Dead', ioWaitId,
                prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 'W') {
            slices.push(new tracing.TimelineSlice('', 'WakeKill', ioWaitId,
                prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 'D|W') {
            slices.push(new tracing.TimelineSlice(
                '', 'Uninterruptable Sleep | WakeKill', ioWaitId,
                prevSlice.end, {}, midDuration));
          } else {
            throw new Error('Unrecognized state: ') +
                prevSlice.args.stateWhenDescheduled;
          }

          slices.push(new tracing.TimelineSlice('', 'Running', runningId,
              nextSlice.start, {}, nextSlice.duration));
        }
        thread.cpuSlices = slices;
      });
    },

    /**
     * Walks the slices stored on this.cpuStates_ and adjusts their timestamps
     * based on any alignment metadata we discovered.
     */
    alignClocks: function(isSecondaryImport) {
      if (this.clockSyncRecords_.length == 0) {
        // If this is a secondary import, and no clock syncing records were
        // found, then abort the import. Otherwise, just skip clock alignment.
        if (!isSecondaryImport)
          return true;

        // Remove the newly imported CPU slices from the model.
        this.abortImport();
        return false;
      }

      // Shift all the slice times based on the sync record.
      var sync = this.clockSyncRecords_[0];
      // NB: parentTS of zero denotes no times-shift; this is
      // used when user and kernel event clocks are identical.
      if (sync.parentTS == 0 || sync.parentTS == sync.perfTS)
        return true;
      var timeShift = sync.parentTS - sync.perfTS;
      for (var cpuNumber in this.cpuStates_) {
        var cpuState = this.cpuStates_[cpuNumber];
        var cpu = cpuState.cpu;

        for (var i = 0; i < cpu.slices.length; i++) {
          var slice = cpu.slices[i];
          slice.start = slice.start + timeShift;
          slice.duration = slice.duration;
        }

        for (var counterName in cpu.counters) {
          var counter = cpu.counters[counterName];
          for (var sI = 0; sI < counter.timestamps.length; sI++)
            counter.timestamps[sI] = (counter.timestamps[sI] + timeShift);
        }
      }
      for (var kernelThreadName in this.kernelThreadStates_) {
        var kthread = this.kernelThreadStates_[kernelThreadName];
        var thread = kthread.thread;
        thread.shiftTimestampsForward(timeShift);
      }
      return true;
    },

    /**
     * Removes any data that has been added to the model because of an error
     * detected during the import.
     */
    abortImport: function() {
      if (this.pushedEventsToThreads)
        throw new Error('Cannot abort, have alrady pushedCpuDataToThreads.');

      for (var cpuNumber in this.cpuStates_)
        delete this.model_.cpus[cpuNumber];
      for (var kernelThreadName in this.kernelThreadStates_) {
        var kthread = this.kernelThreadStates_[kernelThreadName];
        var thread = kthread.thread;
        var process = thread.parent;
        delete process.threads[thread.tid];
        delete this.model_.processes[process.pid];
      }
      this.model_.importErrors.push(
          'Cannot import kernel trace without a clock sync.');
    },

    /**
     * Creates an instance of each registered linux perf event parser.
     * This allows the parsers to register handlers for the events they
     * understand.  We also register our own special handlers (for the
     * timestamp synchronization markers).
     */
    createParsers: function() {
      // Instantiate the parsers; this will register handlers for known events
      var parserConstructors = tracing.LinuxPerfParser.getSubtypeConstructors();
      for (var i = 0; i < parserConstructors.length; ++i) {
        var parserConstructor = parserConstructors[i];
        this.parsers_.push(new parserConstructor(this));
      }

      this.registerEventHandler('tracing_mark_write:trace_event_clock_sync',
          LinuxPerfImporter.prototype.traceClockSyncEvent.bind(this));
      this.registerEventHandler('tracing_mark_write',
          LinuxPerfImporter.prototype.traceMarkingWriteEvent.bind(this));
      // NB: old-style trace markers; deprecated
      this.registerEventHandler('0:trace_event_clock_sync',
          LinuxPerfImporter.prototype.traceClockSyncEvent.bind(this));
      this.registerEventHandler('0',
          LinuxPerfImporter.prototype.traceMarkingWriteEvent.bind(this));
    },

    /**
     * Registers a linux perf event parser used by importCpuData.
     */
    registerEventHandler: function(eventName, handler) {
      // TODO(sleffler) how to handle conflicts?
      this.eventHandlers_[eventName] = handler;
    },

    /**
     * Records the fact that a pid has become runnable. This data will
     * eventually get used to derive each thread's cpuSlices array.
     */
    markPidRunnable: function(ts, pid, comm, prio) {
      // TODO(nduca): implement this functionality.
    },

    importError: function(message) {
      this.model_.importErrors.push('Line ' + (this.lineNumber + 1) +
          ': ' + message);
    },

    /**
     * Processes a trace_event_clock_sync event.
     */
    traceClockSyncEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /parent_ts=(\d+\.?\d*)/.exec(eventBase[2]);
      if (!event)
        return false;

      this.clockSyncRecords_.push({
        perfTS: ts,
        parentTS: event[1] * 1000
      });
      return true;
    },

    /**
     * Processes a trace_marking_write event.
     */
    traceMarkingWriteEvent: function(eventName, cpuNumber, pid, ts, eventBase,
                                     threadName) {
      var event = /^\s*(\w+):\s*(.*)$/.exec(eventBase[5]);
      if (!event) {
        // Check if the event matches events traced by the Android framework
        if (eventBase[5].lastIndexOf('B|', 0) === 0 ||
            eventBase[5] === 'E' ||
            eventBase[5].lastIndexOf('C|', 0) === 0)
          event = [eventBase[5], 'android', eventBase[5]];
        else
          return false;
      }

      var writeEventName = eventName + ':' + event[1];
      var threadName = (/(.+)-\d+/.exec(eventBase[1]))[1];
      var handler = this.eventHandlers_[writeEventName];
      if (!handler) {
        this.importError('Unknown trace_marking_write event ' + writeEventName);
        return true;
      }
      return handler(writeEventName, cpuNumber, pid, ts, event, threadName);
    },

    /**
     * Walks the this.events_ structure and creates TimelineCpu objects.
     */
    importCpuData: function() {
      this.lines_ = this.events_.split('\n');

      var lineRE = null;
      for (this.lineNumber = 0; this.lineNumber < this.lines_.length;
          ++this.lineNumber) {
        var line = this.lines_[this.lineNumber];
        if (line.length == 0 || /^#/.test(line))
          continue;
        if (lineRE == null) {
          lineRE = autoDetectLineRE(line);
          if (lineRE == null) {
            this.importError('Cannot parse line: ' + line);
            continue;
          }
        }
        var eventBase = lineRE.exec(line);
        if (!eventBase) {
          this.importError('Unrecognized line: ' + line);
          continue;
        }

        var pid = parseInt((/.+-(\d+)/.exec(eventBase[1]))[1]);
        var cpuNumber = parseInt(eventBase[2]);
        var ts = parseFloat(eventBase[3]) * 1000;
        var eventName = eventBase[4];

        var handler = this.eventHandlers_[eventName];
        if (!handler) {
          this.importError('Unknown event ' + eventName + ' (' + line + ')');
          continue;
        }
        if (!handler(eventName, cpuNumber, pid, ts, eventBase))
          this.importError('Malformed ' + eventName + ' event (' + line + ')');
      }
    }
  };

  tracing.TimelineModel.registerImporter(LinuxPerfImporter);

  return {
    LinuxPerfImporter: LinuxPerfImporter,
    _LinuxPerfImporterTestExports: TestExports
  };

});
