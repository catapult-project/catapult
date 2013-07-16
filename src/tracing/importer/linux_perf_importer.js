// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * @fileoverview Imports text files in the Linux event trace format into the
 * Tracemodel. This format is output both by sched_trace and by Linux's perf
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
'use strict';

base.require('tracing.trace_model');
base.require('tracing.color_scheme');
base.require('tracing.importer.linux_perf.bus_parser');
base.require('tracing.importer.linux_perf.clock_parser');
base.require('tracing.importer.linux_perf.cpufreq_parser');
base.require('tracing.importer.linux_perf.disk_parser');
base.require('tracing.importer.linux_perf.drm_parser');
base.require('tracing.importer.linux_perf.exynos_parser');
base.require('tracing.importer.linux_perf.gesture_parser');
base.require('tracing.importer.linux_perf.i915_parser');
base.require('tracing.importer.linux_perf.mali_parser');
base.require('tracing.importer.linux_perf.power_parser');
base.require('tracing.importer.linux_perf.sched_parser');
base.require('tracing.importer.linux_perf.sync_parser');
base.require('tracing.importer.linux_perf.workqueue_parser');
base.require('tracing.importer.linux_perf.android_parser');
base.require('tracing.importer.linux_perf.kfunc_parser');

base.exportTo('tracing.importer', function() {
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
     * Switches the active pid on this Cpu. If necessary, add a Slice
     * to the cpu representing the time spent on that Cpu since the last call to
     * switchRunningLinuxPid.
     */
    switchRunningLinuxPid: function(importer, prevState, ts, pid, comm, prio) {
      // Generate a slice if the last active pid was not the idle task
      if (this.lastActivePid !== undefined && this.lastActivePid != 0) {
        var duration = ts - this.lastActiveTs;
        var thread = importer.threadsByLinuxPid[this.lastActivePid];
        var name;
        if (thread)
          name = thread.userFriendlyName;
        else
          name = this.lastActiveComm;

        var slice = new tracing.trace_model.Slice(
            '', name,
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
    this.wakeups_ = [];
    this.kernelThreadStates_ = {};
    this.buildMapFromLinuxPidsToThreads();
    this.lineNumberBase = 0;
    this.lineNumber = -1;
    this.pseudoThreadCounter = 1;
    this.parsers_ = [];
    this.eventHandlers_ = {};
  }

  var TestExports = {};

  // Matches the trace record in 3.2 and later with the print-tgid option:
  //          <idle>-0    0 [001] d...  1.23: sched_switch
  //
  // A TGID (Thread Group ID) is basically what the Linux kernel calls what
  // userland refers to as a process ID (as opposed to a Linux pid, which is
  // what userland calls a thread ID).
  var lineREWithTGID = new RegExp(
      '^\\s*(.+)-(\\d+)\\s+\\(\\s*(\\d+|-+)\\)\\s\\[(\\d+)\\]' +
      '\\s+[dX.][N.][Hhs.][0-9a-f.]' +
      '\\s+(\\d+\\.\\d+):\\s+(\\S+):\\s(.*)$');
  var lineParserWithTGID = function(line) {
    var groups = lineREWithTGID.exec(line);
    if (!groups) {
      return groups;
    }

    var tgid = groups[3];
    if (tgid[0] === '-')
      tgid = undefined;

    return {
      threadName: groups[1],
      pid: groups[2],
      tgid: tgid,
      cpuNumber: groups[4],
      timestamp: groups[5],
      eventName: groups[6],
      details: groups[7]
    };
  };
  TestExports.lineParserWithTGID = lineParserWithTGID;

  // Matches the default trace record in 3.2 and later (includes irq-info):
  //          <idle>-0     [001] d...  1.23: sched_switch
  var lineREWithIRQInfo = new RegExp(
      '^\\s*(.+)-(\\d+)\\s+\\[(\\d+)\\]' +
      '\\s+[dX.][N.][Hhs.][0-9a-f.]' +
      '\\s+(\\d+\\.\\d+):\\s+(\\S+):\\s(.*)$');
  var lineParserWithIRQInfo = function(line) {
    var groups = lineREWithIRQInfo.exec(line);
    if (!groups) {
      return groups;
    }
    return {
      threadName: groups[1],
      pid: groups[2],
      cpuNumber: groups[3],
      timestamp: groups[4],
      eventName: groups[5],
      details: groups[6]
    };
  };
  TestExports.lineParserWithIRQInfo = lineParserWithIRQInfo;

  // Matches the default trace record pre-3.2:
  //          <idle>-0     [001]  1.23: sched_switch
  var lineREWithLegacyFmt =
      /^\s*(.+)-(\d+)\s+\[(\d+)\]\s*(\d+\.\d+):\s+(\S+):\s(.*)$/;
  var lineParserWithLegacyFmt = function(line) {
    var groups = lineREWithLegacyFmt.exec(line);
    if (!groups) {
      return groups;
    }
    return {
      threadName: groups[1],
      pid: groups[2],
      cpuNumber: groups[3],
      timestamp: groups[4],
      eventName: groups[5],
      details: groups[6]
    };
  };
  TestExports.lineParserWithLegacyFmt = lineParserWithLegacyFmt;

  // Matches the trace_event_clock_sync record
  //  0: trace_event_clock_sync: parent_ts=19581477508
  var traceEventClockSyncRE = /trace_event_clock_sync: parent_ts=(\d+\.?\d*)/;
  TestExports.traceEventClockSyncRE = traceEventClockSyncRE;

  // Some kernel trace events are manually classified in slices and
  // hand-assigned a pseudo PID.
  var pseudoKernelPID = 0;

  /**
   * Deduce the format of trace data. Linix kernels prior to 3.3 used one
   * format (by default); 3.4 and later used another.  Additionally, newer
   * kernels can optionally trace the TGID.
   *
   * @return {function} the function for parsing data when the format is
   * recognized; otherwise null.
   */
  function autoDetectLineParser(line) {
    if (line[0] == '{')
      return false;
    if (lineREWithTGID.test(line))
      return lineParserWithTGID;
    if (lineREWithIRQInfo.test(line))
      return lineParserWithIRQInfo;
    if (lineREWithLegacyFmt.test(line))
      return lineParserWithLegacyFmt;
    return null;
  };
  TestExports.autoDetectLineParser = autoDetectLineParser;

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

    if (LinuxPerfImporter._extractEventsFromSystraceHTML(events, false).ok)
      return true;

    if (/^# tracer:/.test(events))
      return true;

    var m = /^(.+)\n/.exec(events);
    if (m)
      events = m[1];
    if (autoDetectLineParser(events))
      return true;

    return false;
  };

  LinuxPerfImporter._extractEventsFromSystraceHTML = function(
      incoming_events, produce_result) {
    var failure = {ok: false};
    if (produce_result === undefined)
      produce_result = true;

    if (/^<!DOCTYPE HTML>/.test(incoming_events) == false)
      return failure;
    var lines = incoming_events.split('\n');
    var cur_line = 1;
    function advanceToLineMatching(regex) {
      for (; cur_line < lines.length; cur_line++) {
        if (regex.test(lines[cur_line]))
          return true;
      }
      return false;
    }

    // Try to find the data...
    if (!advanceToLineMatching(/^  <script>$/))
      return failure;
    if (!advanceToLineMatching(/^  var linuxPerfData = "\\$/))
      return failure;
    var events_begin_at_line = cur_line + 1;

    if (!advanceToLineMatching(/^  <\/script>$/))
      return failure;
    var events_end_at_line = cur_line;

    if (!advanceToLineMatching(/^<\/body>$/))
      return failure;
    if (!advanceToLineMatching(/^<\/html>$/))
      return failure;

    var raw_events = lines.slice(events_begin_at_line,
                                 events_end_at_line);
    function endsWith(str, suffix) {
      return str.indexOf(suffix, str.length - suffix.length) !== -1;
    }
    function stripSuffix(str, suffix) {
      if (!endsWith(str, suffix))
        return str;
      return str.substring(str, str.length - suffix.length);
    }

    // Strip off escaping in the file needed to preserve linebreaks.
    var events = [];
    if (produce_result) {
      for (var i = 0; i < raw_events.length; i++) {
        var event = raw_events[i];
        event = stripSuffix(event, '\\n\\');
        events.push(event);
      }
    } else {
      events = [raw_events[raw_events.length - 1]];
    }

    // Last event ends differently. Strip that off too,
    // treating absence of that trailing stirng as a failure.
    var oldLastEvent = events[events.length - 1];
    var newLastEvent = stripSuffix(oldLastEvent, '\\n";');
    if (newLastEvent == oldLastEvent)
      return failure;
    events[events.length - 1] = newLastEvent;

    return {ok: true,
      lines: produce_result ? events : undefined,
      events_begin_at_line: events_begin_at_line};
  };

  LinuxPerfImporter.prototype = {
    __proto__: Object.prototype,

    extractSubtrace: function() {
      return undefined;
    },

    get model() {
      return this.model_;
    },

    /**
     * Precomputes a lookup table from linux pids back to existing
     * Threads. This is used during importing to add information to each
     * thread about whether it was running, descheduled, sleeping, et
     * cetera.
     */
    buildMapFromLinuxPidsToThreads: function() {
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
        var cpu = this.model_.kernel.getOrCreateCpu(cpuNumber);
        this.cpuStates_[cpuNumber] = new CpuState(cpu);
      }
      return this.cpuStates_[cpuNumber];
    },

    /**
     * @return {TimelinThread} A thread corresponding to the kernelThreadName.
     */
    getOrCreateKernelThread: function(kernelThreadName, pid, tid) {
      if (!this.kernelThreadStates_[kernelThreadName]) {
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
      this.buildMapFromLinuxPidsToThreads();
      this.buildPerThreadCpuSlicesFromCpuState();
    },

    /**
     * Called by the Model after all other importers have imported their
     * events.
     */
    finalizeImport: function() {
    },

    /**
     * Called by the model to join references between objects, after final model
     * bounds have been computed.
     */
    joinRefs: function() {
    },

    /**
     * Builds the cpuSlices array on each thread based on our knowledge of what
     * each Cpu is doing.  This is done only for Threads that are
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

      for (var i in this.wakeups_) {
        var wakeup = this.wakeups_[i];
        var thread = this.threadsByLinuxPid[wakeup.tid];
        if (!thread)
          continue;
        thread.tempWakeups = thread.tempWakeups || [];
        thread.tempWakeups.push(wakeup);
      }

      // Create slices for when the thread is not running.
      var runningId = tracing.getColorIdByName('running');
      var runnableId = tracing.getColorIdByName('runnable');
      var sleepingId = tracing.getColorIdByName('sleeping');
      var ioWaitId = tracing.getColorIdByName('iowait');
      this.model_.getAllThreads().forEach(function(thread) {
        if (thread.tempCpuSlices === undefined)
          return;
        var origSlices = thread.tempCpuSlices;
        delete thread.tempCpuSlices;

        origSlices.sort(function(x, y) {
          return x.start - y.start;
        });

        var wakeups = thread.tempWakeups || [];
        delete thread.tempWakeups;
        wakeups.sort(function(x, y) {
          return x.ts - y.ts;
        });

        // Walk the slice list and put slices between each original slice to
        // show when the thread isn't running.
        var slices = [];

        if (origSlices.length) {
          var slice = origSlices[0];

          if (wakeups.length && wakeups[0].ts < slice.start) {
            var wakeup = wakeups.shift();
            var wakeupDuration = slice.start - wakeup.ts;
            var args = {'wakeup from tid': wakeup.fromTid};
            slices.push(new tracing.trace_model.Slice(
                '', 'Runnable', runnableId, wakeup.ts, args, wakeupDuration));
          }

          slices.push(new tracing.trace_model.Slice('', 'Running', runningId,
              slice.start, {}, slice.duration));
        }

        var wakeup = undefined;
        for (var i = 1; i < origSlices.length; i++) {
          var prevSlice = origSlices[i - 1];
          var nextSlice = origSlices[i];
          var midDuration = nextSlice.start - prevSlice.end;
          while (wakeups.length && wakeups[0].ts < nextSlice.start) {
            var w = wakeups.shift();
            if (wakeup === undefined && w.ts > prevSlice.end) {
              wakeup = w;
            }
          }

          // Push a sleep slice onto the slices list, interrupting it with a
          // wakeup if appropriate.
          var pushSleep = function(title, id) {
            if (wakeup !== undefined) {
              midDuration = wakeup.ts - prevSlice.end;
            }
            slices.push(new tracing.trace_model.Slice(
                '', title, id, prevSlice.end, {}, midDuration));
            if (wakeup !== undefined) {
              var wakeupDuration = nextSlice.start - wakeup.ts;
              var args = {'wakeup from tid': wakeup.fromTid};
              slices.push(new tracing.trace_model.Slice(
                  '', 'Runnable', runnableId, wakeup.ts, args, wakeupDuration));
              wakeup = undefined;
            }
          };

          if (prevSlice.args.stateWhenDescheduled == 'S') {
            pushSleep('Sleeping', sleepingId);
          } else if (prevSlice.args.stateWhenDescheduled == 'R' ||
                     prevSlice.args.stateWhenDescheduled == 'R+') {
            slices.push(new tracing.trace_model.Slice(
                '', 'Runnable', runnableId, prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 'D') {
            pushSleep('Uninterruptible Sleep', ioWaitId);
          } else if (prevSlice.args.stateWhenDescheduled == 'T') {
            slices.push(new tracing.trace_model.Slice('', '__TASK_STOPPED',
                ioWaitId, prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 't') {
            slices.push(new tracing.trace_model.Slice('', 'debug', ioWaitId,
                prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 'Z') {
            slices.push(new tracing.trace_model.Slice('', 'Zombie', ioWaitId,
                prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 'X') {
            slices.push(new tracing.trace_model.Slice('', 'Exit Dead', ioWaitId,
                prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 'x') {
            slices.push(new tracing.trace_model.Slice('', 'Task Dead', ioWaitId,
                prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 'K') {
            slices.push(new tracing.trace_model.Slice('', 'Wakekill', ioWaitId,
                prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 'W') {
            slices.push(new tracing.trace_model.Slice('', 'Waking', ioWaitId,
                prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 'D|K') {
            pushSleep('Uninterruptible Sleep | WakeKill', ioWaitId);
          } else if (prevSlice.args.stateWhenDescheduled == 'D|W') {
            pushSleep('Uninterruptible Sleep | Waking', ioWaitId);
          } else {
            slices.push(new tracing.trace_model.Slice('', 'UNKNOWN', ioWaitId,
                prevSlice.end, {}, midDuration));
            this.model_.importErrors.push('Unrecognized sleep state: ' +
                prevSlice.args.stateWhenDescheduled);
          }

          slices.push(new tracing.trace_model.Slice('', 'Running', runningId,
              nextSlice.start, {}, nextSlice.duration));
        }
        thread.cpuSlices = slices;
      }, this);
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
        delete this.model_.kernel.cpus[cpuNumber];
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
      var parserConstructors =
          tracing.importer.linux_perf.Parser.getSubtypeConstructors();
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
    markPidRunnable: function(ts, pid, comm, prio, fromPid) {
      // The the pids that get passed in to this function are Linux kernel
      // pids, which identify threads.  The rest of trace-viewer refers to
      // these as tids, so the change of nomenclature happens in the following
      // construction of the wakeup object.
      this.wakeups_.push({ts: ts, tid: pid, fromTid: fromPid});
    },

    importError: function(message) {
      this.model_.importErrors.push(
          'Line ' + (this.lineNumberBase + this.lineNumber + 1) +
          ': ' + message);
    },

    /**
     * Processes a trace_event_clock_sync event.
     */
    traceClockSyncEvent: function(eventName, cpuNumber, pid, ts, eventBase) {
      var event = /parent_ts=(\d+\.?\d*)/.exec(eventBase.details);
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
      var event = /^\s*(\w+):\s*(.*)$/.exec(eventBase.details);
      if (!event) {
        // Check if the event matches events traced by the Android framework
        var tag = eventBase.details.substring(0, 2);
        if (tag == 'B|' || tag == 'E' || tag == 'E|' || tag == 'C|' ||
            tag == 'S|' || tag == 'F|') {
          eventBase.subEventName = 'android';
        } else {
          return false;
        }
      } else {
        eventBase.subEventName = event[1];
        eventBase.details = event[2];
      }

      var writeEventName = eventName + ':' + eventBase.subEventName;
      var handler = this.eventHandlers_[writeEventName];
      if (!handler) {
        this.importError('Unknown trace_marking_write event ' + writeEventName);
        return true;
      }
      return handler(writeEventName, cpuNumber, pid, ts, eventBase, threadName);
    },

    /**
     * Walks the this.events_ structure and creates Cpu objects.
     */
    importCpuData: function() {
      var extractResult = LinuxPerfImporter._extractEventsFromSystraceHTML(
          this.events_, true);
      if (extractResult.ok) {
        this.lineNumberBase = extractResult.events_begin_at_line;
        this.lines_ = extractResult.lines;
      } else {
        this.lineNumberBase = 0;
        this.lines_ = this.events_.split('\n');
      }

      var lineParser = null;
      for (this.lineNumber = 0;
           this.lineNumber < this.lines_.length;
          ++this.lineNumber) {
        var line = this.lines_[this.lineNumber];
        if (line.length == 0 || /^#/.test(line))
          continue;
        if (lineParser == null) {
          lineParser = autoDetectLineParser(line);
          if (lineParser == null) {
            this.importError('Cannot parse line: ' + line);
            continue;
          }
        }
        var eventBase = lineParser(line);
        if (!eventBase) {
          this.importError('Unrecognized line: ' + line);
          continue;
        }

        var pid = parseInt(eventBase.pid);
        var cpuNumber = parseInt(eventBase.cpuNumber);
        var ts = parseFloat(eventBase.timestamp) * 1000;
        var eventName = eventBase.eventName;

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

  tracing.TraceModel.registerImporter(LinuxPerfImporter);

  return {
    LinuxPerfImporter: LinuxPerfImporter,
    _LinuxPerfImporterTestExports: TestExports
  };

});
