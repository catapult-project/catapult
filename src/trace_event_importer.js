// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * @fileoverview TraceEventImporter imports TraceEvent-formatted data
 * into the provided timeline model.
 */
cr.define('tracing', function() {
  function ThreadState(tid) {
    this.openSlices = [];
  }

  function TraceEventImporter(model, eventData) {
    this.model_ = model;

    if (typeof(eventData) === 'string' || eventData instanceof String) {
      // If the event data begins with a [, then we know it should end with a ].
      // The reason we check for this is because some tracing implementations
      // cannot guarantee that a ']' gets written to the trace file. So, we are
      // forgiving and if this is obviously the case, we fix it up before
      // throwing the string at JSON.parse.
      if (eventData[0] == '[') {
        n = eventData.length;
        if (eventData[n - 1] != ']' && eventData[n - 1] != '\n') {
          eventData = eventData + ']';
        } else if (eventData[n - 2] != ']' && eventData[n - 1] == '\n') {
          eventData = eventData + ']';
        } else if (eventData[n - 3] != ']' && eventData[n - 2] == '\r' &&
            eventData[n - 1] == '\n') {
          eventData = eventData + ']';
        }
      }
      this.events_ = JSON.parse(eventData);

    } else {
      this.events_ = eventData;
    }

    // Some trace_event implementations put the actual trace events
    // inside a container. E.g { ... , traceEvents: [ ] }
    //
    // If we see that, just pull out the trace events.
    if (this.events_.traceEvents)
      this.events_ = this.events_.traceEvents;

    // To allow simple indexing of threads, we store all the threads by a
    // PTID. A ptid is a pid and tid joined together x:y fashion, eg
    // 1024:130. The ptid is a unique key for a thread in the trace.
    this.threadStateByPTID_ = {};

    // Async events need to be processed durign finalizeEvents
    this.allAsyncEvents_ = [];
  }

  /**
   * @return {boolean} Whether obj is a TraceEvent array.
   */
  TraceEventImporter.canImport = function(eventData) {
    // May be encoded JSON. But we dont want to parse it fully yet.
    // Use a simple heuristic:
    //   - eventData that starts with [ are probably trace_event
    //   - eventData that starts with { are probably trace_event
    // May be encoded JSON. Treat files that start with { as importable by us.
    if (typeof(eventData) === 'string' || eventData instanceof String) {
      return eventData[0] == '{' || eventData[0] == '[';
    }

    // Might just be an array of events
    if (eventData instanceof Array && eventData.length && eventData[0].ph)
      return true;

    // Might be an object with a traceEvents field in it.
    if (eventData.traceEvents)
      return eventData.traceEvents instanceof Array &&
          eventData.traceEvents[0].ph;

    return false;
  };

  TraceEventImporter.prototype = {

    __proto__: Object.prototype,

    /**
     * Helper to process a 'begin' event (e.g. initiate a slice).
     * @param {ThreadState} state Thread state (holds slices).
     * @param {Object} event The current trace event.
     */
    processBeginEvent: function(index, state, event) {
      var colorId = tracing.getStringColorId(event.name);
      var slice =
          { index: index,
            slice: new tracing.TimelineThreadSlice(event.name, colorId,
                                                   event.ts / 1000,
                                                   event.args) };

      if (event.uts)
        slice.slice.startInUserTime = event.uts / 1000;

      if (event.args['ui-nest'] === '0') {
        this.model_.importErrors.push('ui-nest no longer supported.');
        return;
      }

      state.openSlices.push(slice);
    },

    /**
     * Helper to process an 'end' event (e.g. close a slice).
     * @param {ThreadState} state Thread state (holds slices).
     * @param {Object} event The current trace event.
     */
    processEndEvent: function(state, event) {
      if (event.args['ui-nest'] === '0') {
        this.model_.importErrors.push('ui-nest no longer supported.');
        return;
      }
      if (state.openSlices.length == 0) {
        // Ignore E events that are unmatched.
        return;
      }
      var slice = state.openSlices.pop().slice;
      slice.duration = (event.ts / 1000) - slice.start;
      if (event.uts)
        slice.durationInUserTime = (event.uts / 1000) - slice.startInUserTime;
      for (var arg in event.args)
        slice.args[arg] = event.args[arg];

      // Store the slice on the correct subrow.
      var thread = this.model_.getOrCreateProcess(event.pid).
          getOrCreateThread(event.tid);
      var subRowIndex = state.openSlices.length;
      thread.getSubrow(subRowIndex).push(slice);

      // Add the slice to the subSlices array of its parent.
      if (state.openSlices.length) {
        var parentSlice = state.openSlices[state.openSlices.length - 1];
        parentSlice.slice.subSlices.push(slice);
      }
    },

    /**
     * Helper to process an 'async finish' event, which will close an open slice
     * on a TimelineAsyncSliceGroup object.
     **/
    processAsyncEvent: function(index, state, event) {
      var thread = this.model_.getOrCreateProcess(event.pid).
          getOrCreateThread(event.tid);
      this.allAsyncEvents_.push({
        event: event,
        thread: thread});
    },

    /**
     * Helper function that closes any open slices. This happens when a trace
     * ends before an 'E' phase event can get posted. When that happens, this
     * closes the slice at the highest timestamp we recorded and sets the
     * didNotFinish flag to true.
     */
    autoCloseOpenSlices: function() {
      // We need to know the model bounds in order to assign an end-time to
      // the open slices.
      this.model_.updateBounds();

      // The model's max value in the trace is wrong at this point if there are
      // un-closed events. To close those events, we need the true global max
      // value. To compute this, build a list of timestamps that weren't
      // included in the max calculation, then compute the real maximum based on
      // that.
      var openTimestamps = [];
      for (var ptid in this.threadStateByPTID_) {
        var state = this.threadStateByPTID_[ptid];
        for (var i = 0; i < state.openSlices.length; i++) {
          var slice = state.openSlices[i];
          openTimestamps.push(slice.slice.start);
          for (var s = 0; s < slice.slice.subSlices.length; s++) {
            var subSlice = slice.slice.subSlices[s];
            openTimestamps.push(subSlice.start);
            if (subSlice.duration)
              openTimestamps.push(subSlice.end);
          }
        }
      }

      // Figure out the maximum value of model.maxTimestamp and
      // Math.max(openTimestamps). Made complicated by the fact that the model
      // timestamps might be undefined.
      var realMaxTimestamp;
      if (this.model_.maxTimestamp) {
        realMaxTimestamp = Math.max(this.model_.maxTimestamp,
                                    Math.max.apply(Math, openTimestamps));
      } else {
        realMaxTimestamp = Math.max.apply(Math, openTimestamps);
      }

      // Automatically close any slices are still open. These occur in a number
      // of reasonable situations, e.g. deadlock. This pass ensures the open
      // slices make it into the final model.
      for (var ptid in this.threadStateByPTID_) {
        var state = this.threadStateByPTID_[ptid];
        while (state.openSlices.length > 0) {
          var slice = state.openSlices.pop();
          slice.slice.duration = realMaxTimestamp - slice.slice.start;
          slice.slice.didNotFinish = true;
          var event = this.events_[slice.index];

          // Store the slice on the correct subrow.
          var thread = this.model_.getOrCreateProcess(event.pid)
                           .getOrCreateThread(event.tid);
          var subRowIndex = state.openSlices.length;
          thread.getSubrow(subRowIndex).push(slice.slice);

          // Add the slice to the subSlices array of its parent.
          if (state.openSlices.length) {
            var parentSlice = state.openSlices[state.openSlices.length - 1];
            parentSlice.slice.subSlices.push(slice.slice);
          }
        }
      }
    },

    /**
     * Helper that creates and adds samples to a TimelineCounter object based on
     * 'C' phase events.
     */
    processCounterEvent: function(event) {
      var ctr_name;
      if (event.id !== undefined)
        ctr_name = event.name + '[' + event.id + ']';
      else
        ctr_name = event.name;

      var ctr = this.model_.getOrCreateProcess(event.pid)
          .getOrCreateCounter(event.cat, ctr_name);
      // Initialize the counter's series fields if needed.
      if (ctr.numSeries == 0) {
        for (var seriesName in event.args) {
          ctr.seriesNames.push(seriesName);
          ctr.seriesColors.push(
              tracing.getStringColorId(ctr.name + '.' + seriesName));
        }
        if (ctr.numSeries == 0) {
          this.model_.importErrors.push('Expected counter ' + event.name +
              ' to have at least one argument to use as a value.');
          // Drop the counter.
          delete ctr.parent.counters[ctr.name];
          return;
        }
      }

      // Add the sample values.
      ctr.timestamps.push(event.ts / 1000);
      for (var i = 0; i < ctr.numSeries; i++) {
        var seriesName = ctr.seriesNames[i];
        if (event.args[seriesName] === undefined) {
          ctr.samples.push(0);
          continue;
        }
        ctr.samples.push(event.args[seriesName]);
      }
    },

    /**
     * Walks through the events_ list and outputs the structures discovered to
     * model_.
     */
    importEvents: function() {
      // Walk through events
      var events = this.events_;
      // Some events cannot be handled until we have done a first pass over the
      // data set.  So, accumulate them into a temporary data structure.
      var second_pass_events = [];
      for (var eI = 0; eI < events.length; eI++) {
        var event = events[eI];
        var ptid = tracing.TimelineThread.getPTIDFromPidAndTid(
            event.pid, event.tid);

        if (!(ptid in this.threadStateByPTID_))
          this.threadStateByPTID_[ptid] = new ThreadState();
        var state = this.threadStateByPTID_[ptid];

        if (event.ph == 'B') {
          this.processBeginEvent(eI, state, event);
        } else if (event.ph == 'E') {
          this.processEndEvent(state, event);
        } else if (event.ph == 'S') {
          this.processAsyncEvent(eI, state, event);
        } else if (event.ph == 'F') {
          this.processAsyncEvent(eI, state, event);
        } else if (event.ph == 'T') {
          this.processAsyncEvent(eI, state, event);
        } else if (event.ph == 'I') {
          // Treat an Instant event as a duration 0 slice.
          // TimelineSliceTrack's redraw() knows how to handle this.
          this.processBeginEvent(eI, state, event);
          this.processEndEvent(state, event);
        } else if (event.ph == 'C') {
          this.processCounterEvent(event);
        } else if (event.ph == 'M') {
          if (event.name == 'thread_name') {
            var thread = this.model_.getOrCreateProcess(event.pid)
                             .getOrCreateThread(event.tid);
            thread.name = event.args.name;
          } else {
            this.model_.importErrors.push(
                'Unrecognized metadata name: ' + event.name);
          }
        } else {
          this.model_.importErrors.push(
              'Unrecognized event phase: ' + event.ph +
              '(' + event.name + ')');
        }
      }

      // Autoclose any open slices.
      var hasOpenSlices = false;
      for (var ptid in this.threadStateByPTID_) {
        var state = this.threadStateByPTID_[ptid];
        hasOpenSlices |= state.openSlices.length > 0;
      }
      if (hasOpenSlices)
        this.autoCloseOpenSlices();
    },

    /**
     * Called by the TimelineModel after all other importers have imported their
     * events. This function creates async slices for any async events we saw.
     */
    finalizeImport: function() {
      if (this.allAsyncEvents_.length == 0)
        return;

      this.allAsyncEvents_.sort(function(x, y) {
        return x.event.ts - y.event.ts;
      });

      var asyncEventStatesByNameThenID = {};

      var allAsyncEvents = this.allAsyncEvents_;
      for (var i = 0; i < allAsyncEvents.length; i++) {
        var asyncEventState = allAsyncEvents[i];

        var event = asyncEventState.event;
        var name = event.name;
        if (name === undefined) {
          this.model_.importErrors.push(
              'Async events (ph: S, T or F) require an name parameter.');
          continue;
        }

        var id = event.id;
        if (id === undefined) {
          this.model_.importErrors.push(
              'Async events (ph: S, T or F) require an id parameter.');
          continue;
        }

        // TODO(simonjam): Add a synchronous tick on the appropriate thread.

        if (event.ph == 'S') {
          if (asyncEventStatesByNameThenID[name] === undefined)
            asyncEventStatesByNameThenID[name] = {};
          if (asyncEventStatesByNameThenID[name][id]) {
            this.model_.importErrors.push(
                'At ' + event.ts + ', an slice of the same id ' + id +
                ' was alrady open.');
            continue;
          }
          asyncEventStatesByNameThenID[name][id] = [];
          asyncEventStatesByNameThenID[name][id].push(asyncEventState);
        } else {
          if (asyncEventStatesByNameThenID[name] === undefined) {
            this.model_.importErrors.push(
                'At ' + event.ts + ', no slice named ' + name +
                ' was open.');
            continue;
          }
          if (asyncEventStatesByNameThenID[name][id] === undefined) {
            this.model_.importErrors.push(
                'At ' + event.ts + ', no slice named ' + name +
                ' with id=' + id + ' was open.');
            continue;
          }
          var events = asyncEventStatesByNameThenID[name][id];
          events.push(asyncEventState);

          if (event.ph == 'F') {
            // Create a slice from start to end.
            var slice = new tracing.TimelineAsyncSlice(
                name,
                tracing.getStringColorId(name),
                events[0].event.ts / 1000);

            slice.duration = (event.ts / 1000) - (events[0].event.ts / 1000);

            slice.startThread = events[0].thread;
            slice.endThread = asyncEventState.thread;
            slice.id = id;
            slice.args = events[0].event.args;
            slice.subSlices = [];

            // Create subSlices for each step.
            for (var j = 1; j < events.length; ++j) {
              var subName = name;
              if (events[j - 1].event.ph == 'T')
                subName = name + ':' + events[j - 1].event.args.step;
              var subSlice = new tracing.TimelineAsyncSlice(
                  subName,
                  tracing.getStringColorId(name + j),
                  events[j - 1].event.ts / 1000);

              subSlice.duration =
                  (events[j].event.ts / 1000) - (events[j - 1].event.ts / 1000);

              subSlice.startThread = events[j - 1].thread;
              subSlice.endThread = events[j].thread;
              subSlice.id = id;
              subSlice.args = events[j - 1].event.args;

              slice.subSlices.push(subSlice);
            }

            // The args for the finish event go in the last subSlice.
            var lastSlice = slice.subSlices[slice.subSlices.length - 1];
            for (var arg in event.args)
              lastSlice.args[arg] = event.args[arg];

            // Add |slice| to the start-thread's asyncSlices.
            slice.startThread.asyncSlices.push(slice);
            delete asyncEventStatesByNameThenID[name][id];
          }
        }
      }
    }
  };

  tracing.TimelineModel.registerImporter(TraceEventImporter);

  return {
    TraceEventImporter: TraceEventImporter
  };
});
