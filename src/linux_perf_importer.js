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
cr.define('tracing', function() {
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

        var slice = new tracing.TimelineSlice(name,
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
  function LinuxPerfImporter(model, events, isAdditionalImport) {
    this.isAdditionalImport_ = isAdditionalImport;
    this.model_ = model;
    this.events_ = events;
    this.clockSyncRecords_ = [];
    this.cpuStates_ = {};
    this.kernelThreadStates_ = {};
    this.buildMapFromLinuxPidsToTimelineThreads();
    this.lineNumber = -1;
  }

  TestExports = {};

  // Matches the generic trace record:
  //          <idle>-0     [001]  1.23: sched_switch
  var lineRE = /^\s*(.+?)\s+\[(\d+)\]\s*(\d+\.\d+):\s+(\S+):\s(.*)$/;
  TestExports.lineRE = lineRE;

  // Matches the sched_switch record
  var schedSwitchRE = new RegExp(
      'prev_comm=(.+) prev_pid=(\\d+) prev_prio=(\\d+) prev_state=(\\S) ==> ' +
      'next_comm=(.+) next_pid=(\\d+) next_prio=(\\d+)');
  TestExports.schedSwitchRE = schedSwitchRE;

  // Matches the sched_wakeup record
  var schedWakeupRE =
      /comm=(.+) pid=(\d+) prio=(\d+) success=(\d+) target_cpu=(\d+)/;
  TestExports.schedWakeupRE = schedWakeupRE;

  // Matches the trace_event_clock_sync record
  //  0: trace_event_clock_sync: parent_ts=19581477508
  var traceEventClockSyncRE = /trace_event_clock_sync: parent_ts=(\d+\.?\d*)/;
  TestExports.traceEventClockSyncRE = traceEventClockSyncRE;

  // Matches the workqueue_execute_start record
  //  workqueue_execute_start: work struct c7a8a89c: function MISRWrapper
  var workqueueExecuteStartRE = /work struct (.+): function (\S+)/;

  // Matches the workqueue_execute_start record
  //  workqueue_execute_end: work struct c7a8a89c
  var workqueueExecuteEndRE = /work struct (.+)/;

  // Some kernel trace events are manually classified in slices and
  // hand-assigned a pseudo PID+TID.
  var pseudoKernelPID = 0;
  TestExports.pseudoKernelPID = pseudoKernelPID;
  var pseudoI915GemObjectTID = 1;
  TestExports.pseudoI915GemObjectTID = pseudoI915GemObjectTID;
  var pseudoI915GemRingTID = 2;
  TestExports.pseudoI915GemRingTID = pseudoI915GemRingTID;
  var pseudoI915FlipTID = 3;
  TestExports.pseudoI915FlipTID = pseudoI915FlipTID;
  var pseudoI915RegTID = 4;
  TestExports.pseudoI915RegTID = pseudoI915RegTID;
  var pseudoVblankTID = 5;
  TestExports.pseudoVblankTID = pseudoVblankTID;

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

    if (/^# tracer:/.exec(events))
      return true;

    var m = /^(.+)\n/.exec(events);
    if (m)
      events = m[1];
    if (lineRE.exec(events))
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
     * Imports the data in this.events_ into model_.
     */
    importEvents: function() {
      this.importCpuData();
      if (!this.alignClocks())
        return;
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
          slices.push(new tracing.TimelineSlice('Running', runningId,
              slice.start, {}, slice.duration));
        }
        for (var i = 1; i < origSlices.length; i++) {
          var prevSlice = origSlices[i - 1];
          var nextSlice = origSlices[i];
          var midDuration = nextSlice.start - prevSlice.end;
          if (prevSlice.args.stateWhenDescheduled == 'S') {
            slices.push(new tracing.TimelineSlice('Sleeping', sleepingId,
                prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 'R') {
            slices.push(new tracing.TimelineSlice('Runnable', runnableId,
                prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 'D') {
            slices.push(new tracing.TimelineSlice(
              'Uninterruptible Sleep', ioWaitId,
              prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 'T') {
            slices.push(new tracing.TimelineSlice('__TASK_STOPPED', ioWaitId,
                prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 't') {
            slices.push(new tracing.TimelineSlice('debug', ioWaitId,
                prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 'Z') {
            slices.push(new tracing.TimelineSlice('Zombie', ioWaitId,
                prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 'X') {
            slices.push(new tracing.TimelineSlice('Exit Dead', ioWaitId,
                prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 'x') {
            slices.push(new tracing.TimelineSlice('Task Dead', ioWaitId,
                prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 'W') {
            slices.push(new tracing.TimelineSlice('WakeKill', ioWaitId,
                prevSlice.end, {}, midDuration));
          } else if (prevSlice.args.stateWhenDescheduled == 'D|W') {
            slices.push(new tracing.TimelineSlice(
              'Uninterruptable Sleep | WakeKill', ioWaitId,
              prevSlice.end, {}, midDuration));
          } else {
            throw 'Unrecognized state: ' + prevSlice.args.stateWhenDescheduled;
          }

          slices.push(new tracing.TimelineSlice('Running', runningId,
              nextSlice.start, {}, nextSlice.duration));
        }
        thread.cpuSlices = slices;
      });
    },

    /**
     * Walks the slices stored on this.cpuStates_ and adjusts their timestamps
     * based on any alignment metadata we discovered.
     */
    alignClocks: function() {
      if (this.clockSyncRecords_.length == 0) {
        // If this is an additional import, and no clock syncing records were
        // found, then abort the import. Otherwise, just skip clock alignment.
        if (!this.isAdditionalImport_)
          return;

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
        for (var i = 0; i < thread.subRows[0].length; i++) {
          thread.subRows[0][i].start += timeShift;
        }
      }
      return true;
    },

    /**
     * Removes any data that has been added to the model because of an error
     * detected during the import.
     */
    abortImport: function() {
      if (this.pushedEventsToThreads)
        throw 'Cannot abort, have alrady pushedCpuDataToThreads.';

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

    malformedEvent: function(eventName) {
      this.importError('Malformed ' + eventName + ' event');
    },

    cpuStateSlice: function(ts, targetCpuNumber, eventType, cpuState) {
      var targetCpu = this.getOrCreateCpuState(targetCpuNumber);
      var powerCounter;
      if (eventType != '1') {
        this.importError('Don\'t understand power_start events of type ' +
            eventType);
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
      var targetCpu = this.getOrCreateCpuState(targetCpuNumber);
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
      var targetCpu = this.getOrCreateCpuState(targetCpuNumber);
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

    i915GemObjectSlice: function(ts, eventName, obj, args) {
      var kthread = this.getOrCreateKernelThread('i915_gem', pseudoKernelPID,
          pseudoI915GemObjectTID);
      kthread.openSlice = eventName + ':' + obj;
      var slice = new tracing.TimelineSlice(kthread.openSlice,
          tracing.getStringColorId(kthread.openSlice), ts, args, 0);

      kthread.thread.subRows[0].push(slice);
    },

    i915GemRingSlice: function(ts, eventName, dev, ring, args) {
      var kthread = this.getOrCreateKernelThread('i915_gem_ring',
          pseudoKernelPID, pseudoI915GemRingTID);
      kthread.openSlice = eventName + ':' + dev + '.' + ring;
      var slice = new tracing.TimelineSlice(kthread.openSlice,
          tracing.getStringColorId(kthread.openSlice), ts, args, 0);

      kthread.thread.subRows[0].push(slice);
    },

    i915RegSlice: function(ts, eventName, reg, args) {
      var kthread = this.getOrCreateKernelThread('i915_reg',
          pseudoKernelPID, pseudoI915RegTID);
      kthread.openSlice = eventName + ':' + reg;
      var slice = new tracing.TimelineSlice(kthread.openSlice,
          tracing.getStringColorId(kthread.openSlice), ts, args, 0);

      kthread.thread.subRows[0].push(slice);
    },

    i915OpenFlipSlice: function(ts, obj, plane) {
      // use i915_obj_plane?
      var kthread = this.getOrCreateKernelThread('i915_flip',
          pseudoKernelPID, pseudoI915FlipTID);
      kthread.openSliceTS = ts;
      kthread.openSlice = 'flip:' + obj + '/' + plane;
    },

    i915CloseFlipSlice: function(ts, args) {
        // use i915_obj_plane?
        var kthread = this.getOrCreateKernelThread('i915_flip',
            pseudoKernelPID, pseudoI915FlipTID);
        if (kthread.openSlice) {
          var slice = new tracing.TimelineSlice(kthread.openSlice,
              tracing.getStringColorId(kthread.openSlice),
              kthread.openSliceTS,
              args,
              ts - kthread.openSliceTS);

          kthread.thread.subRows[0].push(slice);
        }
        kthread.openSlice = undefined;
    },

    drmVblankSlice: function(ts, eventName, args) {
      var kthread = this.getOrCreateKernelThread('drm_vblank',
          pseudoKernelPID, pseudoVblankTID);
      kthread.openSlice = eventName;
      var slice = new tracing.TimelineSlice(kthread.openSlice,
          tracing.getStringColorId(kthread.openSlice), ts, args, 0);

      kthread.thread.subRows[0].push(slice);
    },

    /**
     * Walks the this.events_ structure and creates TimelineCpu objects.
     */
    importCpuData: function() {
      this.lines_ = this.events_.split('\n');

      for (this.lineNumber = 0; this.lineNumber < this.lines_.length;
          ++this.lineNumber) {
        var line = this.lines_[this.lineNumber];
        if (/^#/.exec(line) || line.length == 0)
          continue;
        var eventBase = lineRE.exec(line);
        if (!eventBase) {
          this.importError('Unrecognized line: ' + line);
          continue;
        }

        var cpuState = this.getOrCreateCpuState(parseInt(eventBase[2]));
        var ts = parseFloat(eventBase[3]) * 1000;

        var eventName = eventBase[4];

        switch (eventName) {
          case 'sched_switch':
            var event = schedSwitchRE.exec(eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }

            var prevState = event[4];
            var nextComm = event[5];
            var nextPid = parseInt(event[6]);
            var nextPrio = parseInt(event[7]);
            cpuState.switchRunningLinuxPid(
                this, prevState, ts, nextPid, nextComm, nextPrio);
            break;
          case 'sched_wakeup':
            var event = schedWakeupRE.exec(eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }

            var comm = event[1];
            var pid = parseInt(event[2]);
            var prio = parseInt(event[3]);
            this.markPidRunnable(ts, pid, comm, prio);
            break;
          case 'power_start':  // NB: old-style power event, deprecated
            var event = /type=(\d+) state=(\d) cpu_id=(\d)+/.exec(eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }

            var targetCpuNumber = parseInt(event[3]);
            var cpuState = parseInt(event[2]);
            this.cpuStateSlice(ts, targetCpuNumber, event[1], cpuState);
            break;
          case 'power_frequency':  // NB: old-style power event, deprecated
            var event = /type=(\d+) state=(\d+) cpu_id=(\d)+/.exec(
                eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }

            var targetCpuNumber = parseInt(event[3]);
            var powerState = parseInt(event[2]);
            this.cpuFrequencySlice(ts, targetCpuNumber, powerState);
            break;
          case 'cpu_frequency':
            var event = /state=(\d+) cpu_id=(\d)+/.exec(eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }

            var targetCpuNumber = parseInt(event[2]);
            var powerState = parseInt(event[1]);
            this.cpuFrequencySlice(ts, targetCpuNumber, powerState);
            break;
          case 'cpu_idle':
            var event = /state=(\d+) cpu_id=(\d)+/.exec(eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }

            var targetCpuNumber = parseInt(event[2]);
            var cpuState = parseInt(event[1]);
            this.cpuIdleSlice(ts, targetCpuNumber, cpuState);
            break;
          case 'workqueue_execute_start':
            var event = workqueueExecuteStartRE.exec(eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }

            var kthread = this.getOrCreateKernelThread(eventBase[1]);
            kthread.openSliceTS = ts;
            kthread.openSlice = event[2];
            break;
          case 'workqueue_execute_end':
            var event = workqueueExecuteEndRE.exec(eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }

            var kthread = this.getOrCreateKernelThread(eventBase[1]);
            if (kthread.openSlice) {
              var slice = new tracing.TimelineSlice(kthread.openSlice,
                  tracing.getStringColorId(kthread.openSlice),
                  kthread.openSliceTS,
                  {},
                  ts - kthread.openSliceTS);

              kthread.thread.subRows[0].push(slice);
            }
            kthread.openSlice = undefined;
            break;
          case 'i915_gem_object_create':
            var event = /obj=(.+), size=(\d+)/.exec(eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }

            var obj = event[1];
            var size = parseInt(event[2]);
            this.i915GemObjectSlice(ts, eventName, obj,
                 {
                   obj: obj,
                   size: size
                 });
            break;
          case 'i915_gem_object_bind':
          case 'i915_gem_object_unbind':
            // TODO(sleffler) mappable
            var event = /obj=(.+), offset=(.+), size=(\d+)/.exec(eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }

            var obj = event[1];
            var offset = event[2];
            var size = parseInt(event[3]);
            this.i915ObjectGemSlice(ts, eventName + ':' + obj,
                {
                  obj: obj,
                  offset: offset,
                  size: size
                });
            break;
          case 'i915_gem_object_change_domain':
            var event = /obj=(.+), read=(.+), write=(.+)/.exec(eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }

            var obj = event[1];
            var read = event[2];
            var write = event[3];
            this.i915GemObjectSlice(ts, eventName, obj,
                {
                  obj: obj,
                  read: read,
                  write: write
                });
            break;
          case 'i915_gem_object_pread':
          case 'i915_gem_object_pwrite':
            var event = /obj=(.+), offset=(\d+), len=(\d+)/.exec(eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }

            var obj = event[1];
            var offset = parseInt(event[2]);
            var len = parseInt(event[3]);
            this.i915GemObjectSlice(ts, eventName, obj,
                {
                  obj: obj,
                  offset: offset,
                  len: len
                });
            break;
          case 'i915_gem_object_fault':
            // TODO(sleffler) writable
            var event = /obj=(.+), (.+) index=(\d+)/.exec(eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }

            var obj = event[1];
            var type = event[2];
            var index = parseInt(event[3]);
            this.i915GemObjectSlice(ts, eventName, obj,
                {
                  obj: obj,
                  type: type,
                  index: index
                });
            break;
          case 'i915_gem_object_clflush':
          case 'i915_gem_object_destroy':
            var event = /obj=(.+)/.exec(eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }

            var obj = event[1];
            this.i915GemObjectSlice(ts, eventName, obj,
                {
                  obj: obj,
                });
            break;
          case 'i915_gem_ring_dispatch':
            var event = /dev=(\d+), ring=(\d+), seqno=(\d+)/.exec(eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }

            var dev = parseInt(event[1]);
            var ring = parseInt(event[2]);
            var seqno = parseInt(event[3]);
            this.i915GemRingSlice(ts, eventName, dev, ring,
                {
                  dev: dev,
                  ring: ring,
                  seqno: seqno
                });
            break;
          case 'i915_gem_ring_flush':
            var event = /dev=(\d+), ring=(\d+), invalidate=(.+), flush=(.+)/.
                exec(eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }

            var dev = parseInt(event[1]);
            var ring = parseInt(event[2]);
            var invalidate = event[3];
            var flush = event[4];
            this.i915GemRingSlice(ts, eventName, dev, ring,
                {
                  dev: dev,
                  ring: ring,
                  invalidate: invalidate,
                  flush: flush
                });
            break;
          case 'i915_gem_request':
          case 'i915_gem_request_add':
          case 'i915_gem_request_complete':
          case 'i915_gem_request_retire':
          case 'i915_gem_request_wait_begin':
          case 'i915_gem_request_wait_end':
            var event = /dev=(\d+), ring=(\d+), seqno=(\d+)/.exec(eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }

            var dev = parseInt(event[1]);
            var ring = parseInt(event[2]);
            var seqno = parseInt(event[3]);
            this.i915GemRingSlice(ts, eventName, dev, ring,
                {
                  dev: dev,
                  ring: ring,
                  seqno: seqno
                });
            break;
          case 'i915_ring_wait_begin':
          case 'i915_ring_wait_end':
            var event = /dev=(\d+), ring=(\d+)/.exec(eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }

            var dev = parseInt(event[1]);
            var ring = parseInt(event[2]);
            this.i915GemRingSlice(ts, eventName, dev, ring,
                {
                  dev: dev,
                  ring: ring
                });
            break;
          case 'i915_gem_object_change_domain':
            var event = /obj=(.+), read=(.+), write=(.+)/.exec(eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }

            var obj = event[1];
            var read = event[2];
            var write = event[3];
            this.i915GemObjectSlice(ts, eventName, obj,
                {
                  obj: obj,
                  read: read,
                  write: write
                });
            break;
          case 'i915_reg_rw':
            var event = /(.+) reg=(.+), len=(.+), val=(.+)/.exec(eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }

            var rw = event[1];
            var reg = event[2];
            var len = event[3];
            var data = event[3];
            this.i915RegSlice(ts, rw, reg,
                {
                  rw: rw,
                  reg: reg,
                  len: len,
                  data: data
                });
            break;
          case 'i915_flip_request':
            var event = /plane=(\d+), obj=(.+)/.exec(eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }

            var plane = parseInt(event[1]);
            var obj = event[2];
            this.i915OpenFlipSlice(ts, obj, plane);
            break;
          case 'i915_flip_complete':
            var event = /plane=(\d+), obj=(.+)/.exec(eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }

            var plane = parseInt(event[1]);
            var obj = event[2];
            this.i915CloseFlipSlice(ts,
                  {
                    obj: obj,
                    plane: plane
                  });
            break;
          case 'drm_vblank_event':
            var event = /crtc=(\d+), seq=(\d+)/.exec(eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }

            var crtc = parseInt(event[1]);
            var seq = parseInt(event[2]);
            this.drmVblankSlice(ts, 'vblank:' + crtc,
                {
                  crtc: crtc,
                  seq: seq
                });
            break;
          case '0':  // NB: old-style trace markers; deprecated
          case 'tracing_mark_write':
            var event = traceEventClockSyncRE.exec(eventBase[5]);
            if (!event) {
              this.malformedEvent(eventName);
              continue;
            }
            this.clockSyncRecords_.push({
              perfTS: ts,
              parentTS: event[1] * 1000
            });
            break;
          default:
            console.log('unknown event ' + eventName);
            break;
        }
      }
    }
  };

  tracing.TimelineModel.registerImporter(LinuxPerfImporter);

  return {
    LinuxPerfImporter: LinuxPerfImporter,
    _LinuxPerfImporterTestExports: TestExports
  };

});
