// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview V8LogImporter imports v8.log files into the provided model.
 */
tvcm.require('tracing.importer.importer');
tvcm.require('tracing.trace_model');
tvcm.require('tracing.trace_model.slice');
tvcm.require('tracing.color_scheme');
tvcm.require('tracing.importer.v8.log_reader');
tvcm.require('tracing.importer.v8.codemap');

tvcm.exportTo('tracing.importer', function() {

  var Importer = tracing.importer.Importer;

  function V8LogImporter(model, eventData) {

    this.importPriority = 3;
    this.model_ = model;

    this.logData_ = eventData;

    this.code_map_ = new tracing.importer.v8.CodeMap();
    this.v8_timer_thread_ = undefined;
    this.v8_stack_thread_ = undefined;
    this.v8_samples_thread_ = undefined;

    // we maintain the timestamp of the last tick to verify if a stack is
    // a continuation from the last sample, or it is a new stack.
    this.last_tick_timestamp_ = undefined;
    // We reconstruct the stack timeline from ticks.
    this.v8_stack_timeline_ = new Array();
  }

  var kV8BinarySuffixes = ['/d8', '/libv8.so'];


  var TimerEventDefaultArgs = {
    'V8.Execute': { pause: false, no_execution: false},
    'V8.External': { pause: false, no_execution: true},
    'V8.CompileFullCode': { pause: true, no_execution: true},
    'V8.RecompileSynchronous': { pause: true, no_execution: true},
    'V8.RecompileParallel': { pause: false, no_execution: false},
    'V8.CompileEval': { pause: true, no_execution: true},
    'V8.Parse': { pause: true, no_execution: true},
    'V8.PreParse': { pause: true, no_execution: true},
    'V8.ParseLazy': { pause: true, no_execution: true},
    'V8.GCScavenger': { pause: true, no_execution: true},
    'V8.GCCompactor': { pause: true, no_execution: true},
    'V8.GCContext': { pause: true, no_execution: true}
  };

  /**
   * @return {boolean} Whether obj is a V8 log string.
   */
  V8LogImporter.canImport = function(eventData) {
    if (typeof(eventData) !== 'string' && !(eventData instanceof String))
      return false;

    return eventData.substring(0, 12) == 'timer-event,' ||
           eventData.substring(0, 5) == 'tick,' ||
           eventData.substring(0, 15) == 'shared-library,' ||
           eventData.substring(0, 9) == 'profiler,' ||
           eventData.substring(0, 14) == 'code-creation,';
  };

  V8LogImporter.prototype = {

    __proto__: Importer.prototype,

    processTimerEvent_: function(name, start, length) {
      var args = TimerEventDefaultArgs[name];
      if (args === undefined) return;
      start /= 1000;  // Convert to milliseconds.
      length /= 1000;
      var colorId = tvcm.ui.getStringColorId(name);
      var slice = new tracing.trace_model.Slice('v8', name, colorId, start,
          args, length);
      this.v8_timer_thread_.sliceGroup.pushSlice(slice);
    },

    processTimerEventStart_: function(name, start) {
      var args = TimerEventDefaultArgs[name];
      if (args === undefined) return;
      start /= 1000;  // Convert to milliseconds.
      this.v8_timer_thread_.sliceGroup.beginSlice('v8', name, start, args);
    },

    processTimerEventEnd_: function(name, end) {
      end /= 1000;  // Convert to milliseconds.
      this.v8_timer_thread_.sliceGroup.endSlice(end);
    },

    processCodeCreateEvent_: function(type, kind, address, size, name) {
      var code_entry = new tracing.importer.v8.CodeMap.CodeEntry(size, name);
      code_entry.kind = kind;
      this.code_map_.addCode(address, code_entry);
    },

    processCodeMoveEvent_: function(from, to) {
      this.code_map_.moveCode(from, to);
    },

    processCodeDeleteEvent_: function(address) {
      this.code_map_.deleteCode(address);
    },

    processSharedLibrary_: function(name, start, end) {
      var code_entry = new tracing.importer.v8.CodeMap.CodeEntry(
          end - start, name);
      code_entry.kind = -3;  // External code kind.
      for (var i = 0; i < kV8BinarySuffixes.length; i++) {
        var suffix = kV8BinarySuffixes[i];
        if (name.indexOf(suffix, name.length - suffix.length) >= 0) {
          code_entry.kind = -1;  // V8 runtime code kind.
          break;
        }
      }
      this.code_map_.addLibrary(start, code_entry);
    },

    findCodeKind_: function(kind) {
      for (name in CodeKinds) {
        if (CodeKinds[name].kinds.indexOf(kind) >= 0) {
          return CodeKinds[name];
        }
      }
    },

    nameForCodeEntry_: function(entry) {
      if (entry)
        return entry.name;
      return 'UnknownCode';
    },

    processTickEvent_: function(pc, start, unused_x, unused_y, vmstate, stack) {
      // Transform ticks into events by aggregating stack frames across ticks
      // For example:
      //
      // Tick Time: 0 1 2 3 4 5 6 7 8 9
      // Stack:     A A A A B B   C C C
      //            D D   E F       G G
      //            H     I           J
      //
      // would become
      //
      // Time:      0 1   3 4 5   7   9
      // Slices:    [  A  ] [B]   [ C ]
      //            [D]   E F       [G]
      //            H     I           J

      var entry = this.code_map_.findEntry(pc);
      var name = this.nameForCodeEntry_(entry);
      start /= 1000;
      this.v8_samples_thread_.addSample('v8', name, start);

      if (stack && stack.length) {
        var stack_frame = this.v8_stack_timeline_;
        for (var i = stack.length - 1; i >= 0; i--) {
          if (!stack[i]) break;
          entry = this.code_map_.findEntry(stack[i]);
          name = this.nameForCodeEntry_(entry);
          if (stack_frame.length > 0 &&
                  stack_frame[stack_frame.length - 1].name == name &&
                  stack_frame[stack_frame.length - 1].end ==
                      this.last_tick_timestamp_) {
            // If the entry from the previous stack at the same level had the
            // same name we extend it to include the current tick as well.
            stack_frame[stack_frame.length - 1].end = start;
          } else {
            // otherwise we create a new entry.
            var record = {
              name: name,
              start: start,
              end: start,
              children: new Array()
            };
            stack_frame.push(record);
          }
          stack_frame = stack_frame[stack_frame.length - 1].children;
        }
        // The last tick time stamp gets updated only when we have a stack
        this.last_tick_timestamp_ = start;
      }
    },

    processDistortion_: function(distortion_in_picoseconds) {
      distortion_per_entry = distortion_in_picoseconds / 1000000;
    },

    processPlotRange_: function(start, end) {
      xrange_start_override = start;
      xrange_end_override = end;
    },

    /**
     * Walks through the events_ list and outputs the structures discovered to
     * model_.
     */
    importEvents: function() {
      var logreader = new tracing.importer.v8.LogReader(
          { 'timer-event' : {
            parsers: [null, parseInt, parseInt],
            processor: this.processTimerEvent_.bind(this)
          },
          'shared-library': {
            parsers: [null, parseInt, parseInt],
            processor: this.processSharedLibrary_.bind(this)
          },
          'timer-event-start' : {
            parsers: [null, parseInt],
            processor: this.processTimerEventStart_.bind(this)
          },
          'timer-event-end' : {
            parsers: [null, parseInt],
            processor: this.processTimerEventEnd_.bind(this)
          },
          'code-creation': {
            parsers: [null, parseInt, parseInt, parseInt, null],
            processor: this.processCodeCreateEvent_.bind(this)
          },
          'code-move': {
            parsers: [parseInt, parseInt],
            processor: this.processCodeMoveEvent_.bind(this)
          },
          'code-delete': {
            parsers: [parseInt],
            processor: this.processCodeDeleteEvent_.bind(this)
          },
          'tick': {
            parsers: [parseInt, parseInt, null, null, parseInt, 'var-args'],
            processor: this.processTickEvent_.bind(this)
          },
          'distortion': {
            parsers: [parseInt],
            processor: this.processDistortion_.bind(this)
          },
          'plot-range': {
            parsers: [parseInt, parseInt],
            processor: this.processPlotRange_.bind(this)
          }
          });

      this.v8_timer_thread_ =
          this.model_.getOrCreateProcess(-32).getOrCreateThread(1);
      this.v8_timer_thread_.name = 'V8 Timers';
      this.v8_stack_thread_ =
          this.model_.getOrCreateProcess(-32).getOrCreateThread(2);
      this.v8_stack_thread_.name = 'V8 JavaScript';
      this.v8_samples_thread_ =
          this.model_.getOrCreateProcess(-32).getOrCreateThread(3);
      this.v8_samples_thread_.name = 'V8 PC';

      var lines = this.logData_.split('\n');
      for (var i = 0; i < lines.length; i++) {
        logreader.processLogLine(lines[i]);
      }

      function addSlices(slices, thread) {
        for (var i = 0; i < slices.length; i++) {
          var duration = slices[i].end - slices[i].start;
          var slice = new tracing.trace_model.Slice('v8', slices[i].name,
              tvcm.ui.getStringColorId(slices[i].name),
              slices[i].start, {}, duration);
          thread.sliceGroup.pushSlice(slice);
          addSlices(slices[i].children, thread);
        }
      }
      addSlices(this.v8_stack_timeline_, this.v8_stack_thread_);
    }
  };

  tracing.TraceModel.registerImporter(V8LogImporter);

  return {
    V8LogImporter: V8LogImporter
  };
});
