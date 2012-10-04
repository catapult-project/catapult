// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * @fileoverview TraceEventImporter imports TraceEvent-formatted data
 * into the provided timeline model.
 */
base.require('timeline_model');
base.require('timeline_color_scheme');
base.exportTo('tracing', function() {

  function TraceEventImporter(model, eventData) {
    this.importPriority = 1;
    this.model_ = model;

    if (typeof(eventData) === 'string' || eventData instanceof String) {
      // If the event data begins with a [, then we know it should end with a ].
      // The reason we check for this is because some tracing implementations
      // cannot guarantee that a ']' gets written to the trace file. So, we are
      // forgiving and if this is obviously the case, we fix it up before
      // throwing the string at JSON.parse.
      if (eventData[0] == '[') {
        n = eventData.length;
        if (eventData[n - 1] == '\n') {
          eventData = eventData.substring(0, n - 1);
          n--;

          if (eventData[n - 1] == '\r') {
            eventData = eventData.substring(0, n - 1);
            n--;
          }
        }

        if (eventData[n - 1] == ',')
          eventData = eventData.substring(0, n - 1);
        if (eventData[n - 1] != ']')
          eventData = eventData + ']';
      }

      this.events_ = JSON.parse(eventData);

    } else {
      this.events_ = eventData;
    }

    // Some trace_event implementations put the actual trace events
    // inside a container. E.g { ... , traceEvents: [ ] }
    // If we see that, just pull out the trace events.
    if (this.events_.traceEvents) {
      this.events_ = this.events_.traceEvents;
      for (fieldName in this.events_) {
        if (fieldName == 'traceEvents')
          continue;
        this.model_.metadata.push({name: fieldName,
          value: this.events_[fieldName]});
      }
    }

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
     * Helper to process an 'async finish' event, which will close an open slice
     * on a TimelineAsyncSliceGroup object.
     */
    processAsyncEvent: function(index, event) {
      var thread = this.model_.getOrCreateProcess(event.pid).
          getOrCreateThread(event.tid);
      this.allAsyncEvents_.push({
        event: event,
        thread: thread});
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
        if (event.ph == 'B') {
          var thread = this.model_.getOrCreateProcess(event.pid)
            .getOrCreateThread(event.tid);
          if (!thread.isTimestampValidForBeginOrEnd(event.ts / 1000)) {
            this.model_.importErrors.push(
                'Timestamps are moving backward.');
            continue;
          }
          thread.beginSlice(event.cat, event.name, event.ts / 1000, event.args);
        } else if (event.ph == 'E') {
          var thread = this.model_.getOrCreateProcess(event.pid)
            .getOrCreateThread(event.tid);
          if (!thread.isTimestampValidForBeginOrEnd(event.ts / 1000)) {
            this.model_.importErrors.push(
                'Timestamps are moving backward.');
            continue;
          }
          if (!thread.openSliceCount) {
            this.model_.importErrors.push(
                'E phase event without a matching B phase event.');
            continue;
          }

          var slice = thread.endSlice(event.ts / 1000);
          for (var arg in event.args) {
            if (slice.args[arg] !== undefined) {
              this.model_.importErrors.push(
                  'Both the B and E phases of ' + slice.name +
                  'provided values for argument ' + arg + '. ' +
                  'The value of the E phase event will be used.');
            }
            slice.args[arg] = event.args[arg];
          }

        } else if (event.ph == 'S') {
          this.processAsyncEvent(eI, event);
        } else if (event.ph == 'F') {
          this.processAsyncEvent(eI, event);
        } else if (event.ph == 'T') {
          this.processAsyncEvent(eI, event);
        } else if (event.ph == 'I') {
          // Treat an Instant event as a duration 0 slice.
          // TimelineSliceTrack's redraw() knows how to handle this.
          var thread = this.model_.getOrCreateProcess(event.pid)
            .getOrCreateThread(event.tid);
          thread.beginSlice(event.cat, event.name, event.ts / 1000, event.args);
          thread.endSlice(event.ts / 1000);
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
        } else if (event.ph == 's') {
          // NB: toss until there's proper support
        } else if (event.ph == 't') {
          // NB: toss until there's proper support
        } else if (event.ph == 'f') {
          // NB: toss until there's proper support
        } else {
          this.model_.importErrors.push(
              'Unrecognized event phase: ' + event.ph +
              '(' + event.name + ')');
        }
      }
    },

    /**
     * Called by the TimelineModel after all other importers have imported their
     * events.
     */
    finalizeImport: function() {
      this.createAsyncSlices_();
    },

    createAsyncSlices_: function() {
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
                'At ' + event.ts + ', a slice of the same id ' + id +
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
                events[0].event.cat,
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
                  events[0].event.cat,
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
