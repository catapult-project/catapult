// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview TraceEventImporter imports TraceEvent-formatted data
 * into the provided model.
 */
tvcm.require('tvcm.quad');
tvcm.require('tracing.trace_model');
tvcm.require('tracing.color_scheme');
tvcm.require('tracing.importer.importer');
tvcm.require('tracing.trace_model.instant_event');
tvcm.require('tracing.trace_model.flow_event');
tvcm.require('tracing.trace_model.counter_series');

tvcm.exportTo('tracing.importer', function() {

  var Importer = tracing.importer.Importer;

  function deepCopy(value) {
    if (!(value instanceof Object)) {
      if (value === undefined || value === null)
        return value;
      if (typeof value == 'string')
        return value.substring();
      if (typeof value == 'boolean')
        return value;
      if (typeof value == 'number')
        return value;
      throw new Error('Unrecognized: ' + typeof value);
    }

    var object = value;
    if (object instanceof Array) {
      var res = new Array(object.length);
      for (var i = 0; i < object.length; i++)
        res[i] = deepCopy(object[i]);
      return res;
    }

    if (object.__proto__ != Object.prototype)
      throw new Error('Can only clone simple types');
    var res = {};
    for (var key in object) {
      res[key] = deepCopy(object[key]);
    }
    return res;
  }

  function TraceEventImporter(model, eventData) {
    this.importPriority = 1;
    this.model_ = model;
    this.events_ = undefined;
    this.systemTraceEvents_ = undefined;
    this.eventsWereFromString_ = false;
    this.allAsyncEvents_ = [];
    this.allFlowEvents_ = [];
    this.allObjectEvents_ = [];

    if (typeof(eventData) === 'string' || eventData instanceof String) {
      // If the event data begins with a [, then we know it should end with a ].
      // The reason we check for this is because some tracing implementations
      // cannot guarantee that a ']' gets written to the trace file. So, we are
      // forgiving and if this is obviously the case, we fix it up before
      // throwing the string at JSON.parse.
      if (eventData[0] === '[') {
        eventData = eventData.replace(/[\r|\n]*$/, '')
                             .replace(/\s*,\s*$/, '');
        if (eventData[eventData.length - 1] !== ']')
          eventData = eventData + ']';
      }
      this.events_ = JSON.parse(eventData);
      this.eventsWereFromString_ = true;
    } else {
      this.events_ = eventData;
    }

    // Some trace_event implementations put the actual trace events
    // inside a container. E.g { ... , traceEvents: [ ] }
    // If we see that, just pull out the trace events.
    if (this.events_.traceEvents) {
      var container = this.events_;
      this.events_ = this.events_.traceEvents;

      // Some trace_event implementations put linux_perf_importer traces as a
      // huge string inside container.systemTraceEvents. If we see that, pull it
      // out. It will be picked up by extractSubtraces later on.
      this.systemTraceEvents_ = container.systemTraceEvents;

      // Any other fields in the container should be treated as metadata.
      for (var fieldName in container) {
        if (fieldName === 'traceEvents' || fieldName === 'systemTraceEvents')
          continue;
        this.model_.metadata.push({name: fieldName,
          value: container[fieldName]});
      }
    }
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

    __proto__: Importer.prototype,

    extractSubtraces: function() {
      var tmp = this.systemTraceEvents_;
      this.systemTraceEvents_ = undefined;
      return tmp ? [tmp] : [];
    },

    /**
     * Deep copying is only needed if the trace was given to us as events.
     */
    deepCopyIfNeeded_: function(obj) {
      if (obj === undefined)
        obj = {};
      if (this.eventsWereFromString_)
        return obj;
      return deepCopy(obj);
    },

    /**
     * Helper to process an async event.
     */
    processAsyncEvent: function(event) {
      var thread = this.model_.getOrCreateProcess(event.pid).
          getOrCreateThread(event.tid);
      this.allAsyncEvents_.push({
        sequenceNumber: this.allAsyncEvents_.length,
        event: event,
        thread: thread});
    },

    /**
     * Helper to process a flow event.
     */
    processFlowEvent: function(event) {
      var thread = this.model_.getOrCreateProcess(event.pid).
          getOrCreateThread(event.tid);
      this.allFlowEvents_.push({
        sequenceNumber: this.allFlowEvents_.length,
        event: event,
        thread: thread
      });
    },

    /**
     * Helper that creates and adds samples to a Counter object based on
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
      if (ctr.numSeries === 0) {
        for (var seriesName in event.args) {
          ctr.addSeries(new tracing.trace_model.CounterSeries(seriesName,
              tvcm.ui.getStringColorId(ctr.name + '.' + seriesName)));
        }

        if (ctr.numSeries === 0) {
          this.model_.importWarning({
            type: 'counter_parse_error',
            message: 'Expected counter ' + event.name +
                ' to have at least one argument to use as a value.'
          });

          // Drop the counter.
          delete ctr.parent.counters[ctr.name];
          return;
        }
      }

      var ts = event.ts / 1000;
      ctr.series.forEach(function(series) {
        var val = event.args[series.name] ? event.args[series.name] : 0;
        series.addCounterSample(ts, val);
      });
    },

    processObjectEvent: function(event) {
      var thread = this.model_.getOrCreateProcess(event.pid).
          getOrCreateThread(event.tid);
      this.allObjectEvents_.push({
        sequenceNumber: this.allObjectEvents_.length,
        event: event,
        thread: thread});
    },

    processDurationEvent: function(event) {
      var thread = this.model_.getOrCreateProcess(event.pid)
        .getOrCreateThread(event.tid);
      if (!thread.sliceGroup.isTimestampValidForBeginOrEnd(event.ts / 1000)) {
        this.model_.importWarning({
          type: 'duration_parse_error',
          message: 'Timestamps are moving backward.'
        });
        return;
      }

      if (event.ph == 'B') {
        thread.sliceGroup.beginSlice(event.cat, event.name, event.ts / 1000,
                                     this.deepCopyIfNeeded_(event.args),
                                     event.tts / 1000);
      } else {
        if (!thread.sliceGroup.openSliceCount) {
          this.model_.importWarning({
            type: 'duration_parse_error',
            message: 'E phase event without a matching B phase event.'
          });
          return;
        }

        var slice = thread.sliceGroup.endSlice(event.ts / 1000,
                                               event.tts / 1000);
        if (event.name && slice.title != event.name) {
          this.model_.importWarning({
            type: 'title_match_error',
            message: 'Titles do not match. Title is ' +
                slice.title + ' in openSlice, and is ' +
                event.name + ' in endSlice'
          });
        }
        for (var arg in event.args) {
          if (slice.args[arg] !== undefined) {
            this.model_.importWarning({
              type: 'duration_parse_error',
              message: 'Both the B and E phases of ' + slice.name +
                  ' provided values for argument ' + arg + '.' +
                  ' The value of the E phase event will be used.'
            });
          }
          slice.args[arg] = this.deepCopyIfNeeded_(event.args[arg]);
        }
      }
    },

    processCompleteEvent: function(event) {
      var thread = this.model_.getOrCreateProcess(event.pid)
          .getOrCreateThread(event.tid);
      thread.sliceGroup.pushCompleteSlice(event.cat, event.name,
          event.ts / 1000,
          event.dur === undefined ? undefined : event.dur / 1000,
          event.tts === undefined ? undefined : event.tts / 1000,
          event.tdur === undefined ? undefined : event.tdur / 1000,
          this.deepCopyIfNeeded_(event.args));
    },

    processMetadataEvent: function(event) {
      if (event.name == 'process_name') {
        var process = this.model_.getOrCreateProcess(event.pid);
        process.name = event.args.name;
      } else if (event.name == 'process_labels') {
        var process = this.model_.getOrCreateProcess(event.pid);
        var labels = event.args.labels.split(',');
        for (var i = 0; i < labels.length; i++)
          process.addLabelIfNeeded(labels[i]);
      } else if (event.name == 'process_sort_index') {
        var process = this.model_.getOrCreateProcess(event.pid);
        process.sortIndex = event.args.sort_index;
      } else if (event.name == 'thread_name') {
        var thread = this.model_.getOrCreateProcess(event.pid).
            getOrCreateThread(event.tid);
        thread.name = event.args.name;
      } else if (event.name == 'thread_sort_index') {
        var thread = this.model_.getOrCreateProcess(event.pid).
            getOrCreateThread(event.tid);
        thread.sortIndex = event.args.sort_index;
      } else {
        this.model_.importWarning({
          type: 'metadata_parse_error',
          message: 'Unrecognized metadata name: ' + event.name
        });
      }
    },

    // Treat an Instant event as a duration 0 slice.
    // SliceTrack's redraw() knows how to handle this.
    processInstantEvent: function(event) {
      var constructor;
      switch (event.s) {
        case 'g':
          constructor = tracing.trace_model.GlobalInstantEvent;
          break;
        case 'p':
          constructor = tracing.trace_model.ProcessInstantEvent;
          break;
        case 't':
          // fall through
        default:
          // Default to thread to support old style input files.
          constructor = tracing.trace_model.ThreadInstantEvent;
          break;
      }

      var colorId = tvcm.ui.getStringColorId(event.name);
      var instantEvent = new constructor(event.cat, event.name,
          colorId, event.ts / 1000, this.deepCopyIfNeeded_(event.args));

      switch (instantEvent.type) {
        case tracing.trace_model.InstantEventType.GLOBAL:
          this.model_.pushInstantEvent(instantEvent);
          break;

        case tracing.trace_model.InstantEventType.PROCESS:
          var process = this.model_.getOrCreateProcess(event.pid);
          process.pushInstantEvent(instantEvent);
          break;

        case tracing.trace_model.InstantEventType.THREAD:
          var thread = this.model_.getOrCreateProcess(event.pid)
              .getOrCreateThread(event.tid);
          thread.sliceGroup.pushInstantEvent(instantEvent);
          break;
        default:
          throw new Error('Unknown instant event type: ' + event.s);
      }
    },

    processSampleEvent: function(event) {
      var thread = this.model_.getOrCreateProcess(event.pid)
        .getOrCreateThread(event.tid);
      thread.addSample(event.cat, event.name, event.ts / 1000,
                       this.deepCopyIfNeeded_(event.args));
    },

    /**
     * Walks through the events_ list and outputs the structures discovered to
     * model_.
     */
    importEvents: function() {
      var events = this.events_;
      for (var eI = 0; eI < events.length; eI++) {
        var event = events[eI];
        if (event.ph === 'B' || event.ph === 'E') {
          this.processDurationEvent(event);

        } else if (event.ph === 'X') {
          this.processCompleteEvent(event);

        } else if (event.ph === 'S' || event.ph === 'F' || event.ph === 'T' ||
                   event.ph === 'p') {
          this.processAsyncEvent(event);

        // Note, I is historic. The instant event marker got changed, but we
        // want to support loading old trace files so we have both I and i.
        } else if (event.ph == 'I' || event.ph == 'i') {
          this.processInstantEvent(event);

        } else if (event.ph == 'P') {
          this.processSampleEvent(event);

        } else if (event.ph == 'C') {
          this.processCounterEvent(event);

        } else if (event.ph == 'M') {
          this.processMetadataEvent(event);

        } else if (event.ph === 'N' || event.ph === 'D' || event.ph === 'O') {
          this.processObjectEvent(event);

        } else if (event.ph === 's' || event.ph === 't' || event.ph === 'f') {
          this.processFlowEvent(event);

        } else {
          this.model_.importWarning({
            type: 'parse_error',
            message: 'Unrecognized event phase: ' +
                event.ph + ' (' + event.name + ')'
          });
        }
      }
    },

    /**
     * Called by the Model after all other importers have imported their
     * events.
     */
    finalizeImport: function() {
      this.createAsyncSlices_();
      this.createFlowSlices_();
      this.createExplicitObjects_();
      this.createImplicitObjects_();
    },

    /**
     * Called by the model to join references between objects, after final model
     * bounds have been computed.
     */
    joinRefs: function() {
      this.joinObjectRefs_();
    },

    createAsyncSlices_: function() {
      if (this.allAsyncEvents_.length === 0)
        return;

      this.allAsyncEvents_.sort(function(x, y) {
        var d = x.event.ts - y.event.ts;
        if (d != 0)
          return d;
        return x.sequenceNumber - y.sequenceNumber;
      });

      var asyncEventStatesByNameThenID = {};

      var allAsyncEvents = this.allAsyncEvents_;
      for (var i = 0; i < allAsyncEvents.length; i++) {
        var asyncEventState = allAsyncEvents[i];

        var event = asyncEventState.event;
        var name = event.name;
        if (name === undefined) {
          this.model_.importWarning({
            type: 'async_slice_parse_error',
            message: 'Async events (ph: S, T, p, or F) require a name ' +
                ' parameter.'
          });
          continue;
        }

        var id = event.id;
        if (id === undefined) {
          this.model_.importWarning({
            type: 'async_slice_parse_error',
            message: 'Async events (ph: S, T, p, or F) require an id parameter.'
          });
          continue;
        }

        // TODO(simonjam): Add a synchronous tick on the appropriate thread.

        if (event.ph === 'S') {
          if (asyncEventStatesByNameThenID[name] === undefined)
            asyncEventStatesByNameThenID[name] = {};
          if (asyncEventStatesByNameThenID[name][id]) {
            this.model_.importWarning({
              type: 'async_slice_parse_error',
              message: 'At ' + event.ts + ', a slice of the same id ' + id +
                  ' was alrady open.'
            });
            continue;
          }
          asyncEventStatesByNameThenID[name][id] = [];
          asyncEventStatesByNameThenID[name][id].push(asyncEventState);
        } else {
          if (asyncEventStatesByNameThenID[name] === undefined) {
            this.model_.importWarning({
              type: 'async_slice_parse_error',
              message: 'At ' + event.ts + ', no slice named ' + name +
                  ' was open.'
            });
            continue;
          }
          if (asyncEventStatesByNameThenID[name][id] === undefined) {
            this.model_.importWarning({
              type: 'async_slice_parse_error',
              message: 'At ' + event.ts + ', no slice named ' + name +
                  ' with id=' + id + ' was open.'
            });
            continue;
          }
          var events = asyncEventStatesByNameThenID[name][id];
          events.push(asyncEventState);

          if (event.ph === 'F') {
            // Create a slice from start to end.
            var slice = new tracing.trace_model.AsyncSlice(
                events[0].event.cat,
                name,
                tvcm.ui.getStringColorId(name),
                events[0].event.ts / 1000);

            slice.duration = (event.ts / 1000) - (events[0].event.ts / 1000);

            slice.startThread = events[0].thread;
            slice.endThread = asyncEventState.thread;
            slice.id = id;
            slice.args = this.deepCopyIfNeeded_(events[0].event.args);
            slice.subSlices = [];

            var stepType = events[1].event.ph;
            var isValid = true;

            // Create subSlices for each step.
            for (var j = 1; j < events.length; ++j) {
              var subName = name;
              if (events[j].event.ph == 'T' || events[j].event.ph == 'p') {
                isValid = this.assertStepTypeMatches_(stepType, events[j]);
                if (!isValid)
                  break;
              }

              var targetEvent;
              if (stepType == 'T') {
                targetEvent = events[j - 1];
              } else {
                targetEvent = events[j];
              }

              var subName = events[0].event.name;
              if (targetEvent.event.ph == 'T' || targetEvent.event.ph == 'p')
                subName = subName + ':' + targetEvent.event.args.step;

              var subSlice = new tracing.trace_model.AsyncSlice(
                  events[0].event.cat,
                  subName,
                  tvcm.ui.getStringColorId(subName + j),
                  events[j - 1].event.ts / 1000);

              subSlice.duration =
                  (events[j].event.ts / 1000) - (events[j - 1].event.ts / 1000);

              subSlice.startThread = events[j - 1].thread;
              subSlice.endThread = events[j].thread;
              subSlice.id = id;
              subSlice.args = tvcm.concatenateObjects(events[0].event.args,
                                                      targetEvent.event.args);

              slice.subSlices.push(subSlice);

              if (events[j].event.ph == 'F' && stepType == 'T') {
                // The args for the finish event go in the last subSlice.
                var lastSlice = slice.subSlices[slice.subSlices.length - 1];
                lastSlice.args = tvcm.concatenateObjects(lastSlice.args,
                                                         event.args);
              }
            }

            if (isValid) {
              // Add |slice| to the start-thread's asyncSlices.
              slice.startThread.asyncSliceGroup.push(slice);
            }

            delete asyncEventStatesByNameThenID[name][id];
          }
        }
      }
    },

    assertStepTypeMatches_: function(stepType, event) {
      if (stepType != event.event.ph) {
        this.model_.importWarning({
          type: 'async_slice_parse_error',
          message: 'At ' + event.event.ts + ', a slice named ' +
              event.event.name + ' with id=' + event.event.id +
              ' had both begin and end steps, which is not allowed.'
        });
        return false;
      }
      return true;
    },

    createFlowSlices_: function() {
      if (this.allFlowEvents_.length === 0)
        return;

      this.allFlowEvents_.sort(function(x, y) {
        var d = x.event.ts - y.event.ts;
        if (d != 0)
          return d;
        return x.sequenceNumber - y.sequenceNumber;
      });

      var flowIdToEvent = {};
      for (var i = 0; i < this.allFlowEvents_.length; ++i) {
        var data = this.allFlowEvents_[i];
        var event = data.event;
        var thread = data.thread;

        if (event.name === undefined) {
          this.model_.importWarning({
            type: 'flow_slice_parse_error',
            message: 'Flow events (ph: s, t or f) require a name parameter.'
          });
          continue;
        }

        if (event.id === undefined) {
          this.model_.importWarning({
            type: 'flow_slice_parse_error',
            message: 'Flow events (ph: s, t or f) require an id parameter.'
          });
          continue;
        }

        var slice = new tracing.trace_model.FlowEvent(
            event.cat,
            event.id,
            event.name,
            tvcm.ui.getStringColorId(event.name),
            event.ts / 1000,
            this.deepCopyIfNeeded_(event.args));
        thread.sliceGroup.pushSlice(slice);

        if (event.ph === 's') {
          if (flowIdToEvent[event.id] !== undefined) {
            this.model_.importWarning({
              type: 'flow_slice_start_error',
              message: 'event id ' + event.id + ' already seen when ' +
                  'encountering start of flow event.'});
          }
          flowIdToEvent[event.id] = slice;

        } else if (event.ph === 't' || event.ph === 'f') {
          var flowPosition = flowIdToEvent[event.id];
          if (flowPosition === undefined) {
            this.model_.importWarning({
              type: 'flow_slice_ordering_error',
              message: 'Found flow phase ' + event.ph + ' for id: ' + event.id +
                  ' but no flow start found.'
            });
            continue;
          }
          this.model_.flowEvents.push([flowPosition, slice]);

          if (flowPosition)
            flowPosition.nextFlowEvent = slice;
          if (slice)
            slice.previousFlowEvent = flowPosition;

          if (event.ph === 'f') {
            flowIdToEvent[event.id] = undefined;
          } else {
            // Make this slice the next start event in this flow.
            flowIdToEvent[event.id] = slice;
          }
        }
      }
    },

    /**
     * This function creates objects described via the N, D, and O phase
     * events.
     */
    createExplicitObjects_: function() {
      if (this.allObjectEvents_.length == 0)
        return;

      function processEvent(objectEventState) {
        var event = objectEventState.event;
        var thread = objectEventState.thread;
        if (event.name === undefined) {
          this.model_.importWarning({
            type: 'object_parse_error',
            message: 'While processing ' + JSON.stringify(event) + ': ' +
                'Object events require an name parameter.'
          });
        }

        if (event.id === undefined) {
          this.model_.importWarning({
            type: 'object_parse_error',
            message: 'While processing ' + JSON.stringify(event) + ': ' +
                'Object events require an id parameter.'
          });
        }
        var process = thread.parent;
        var ts = event.ts / 1000;
        var instance;
        if (event.ph == 'N') {
          try {
            instance = process.objects.idWasCreated(
                event.id, event.cat, event.name, ts);
          } catch (e) {
            this.model_.importWarning({
              type: 'object_parse_error',
              message: 'While processing create of ' +
                  event.id + ' at ts=' + ts + ': ' + e
            });
            return;
          }
        } else if (event.ph == 'O') {
          if (event.args.snapshot === undefined) {
            this.model_.importWarning({
              type: 'object_parse_error',
              message: 'While processing ' + event.id + ' at ts=' + ts + ': ' +
                  'Snapshots must have args: {snapshot: ...}'
            });
            return;
          }
          var snapshot;
          try {
            var args = this.deepCopyIfNeeded_(event.args.snapshot);
            var cat;
            if (args.cat) {
              cat = args.cat;
              delete args.cat;
            } else {
              cat = event.cat;
            }

            var baseTypename;
            if (args.base_type) {
              baseTypename = args.base_type;
              delete args.base_type;
            } else {
              baseTypename = undefined;
            }
            snapshot = process.objects.addSnapshot(
                event.id, cat, event.name, ts,
                args, baseTypename);
          } catch (e) {
            this.model_.importWarning({
              type: 'object_parse_error',
              message: 'While processing snapshot of ' +
                  event.id + ' at ts=' + ts + ': ' + e
            });
            return;
          }
          instance = snapshot.objectInstance;
        } else if (event.ph == 'D') {
          try {
            instance = process.objects.idWasDeleted(
                event.id, event.cat, event.name, ts);
          } catch (e) {
            this.model_.importWarning({
              type: 'object_parse_error',
              message: 'While processing delete of ' +
                  event.id + ' at ts=' + ts + ': ' + e
            });
            return;
          }
        }

        if (instance)
          instance.colorId = tvcm.ui.getStringColorId(instance.typeName);
      }

      this.allObjectEvents_.sort(function(x, y) {
        var d = x.event.ts - y.event.ts;
        if (d != 0)
          return d;
        return x.sequenceNumber - y.sequenceNumber;
      });

      var allObjectEvents = this.allObjectEvents_;
      for (var i = 0; i < allObjectEvents.length; i++) {
        var objectEventState = allObjectEvents[i];
        try {
          processEvent.call(this, objectEventState);
        } catch (e) {
          this.model_.importWarning({
            type: 'object_parse_error',
            message: e.message
          });
        }
      }
    },

    createImplicitObjects_: function() {
      tvcm.iterItems(this.model_.processes, function(pid, process) {
        this.createImplicitObjectsForProcess_(process);
      }, this);
    },

    // Here, we collect all the snapshots that internally contain a
    // Javascript-level object inside their args list that has an "id" field,
    // and turn that into a snapshot of the instance referred to by id.
    createImplicitObjectsForProcess_: function(process) {

      function processField(referencingObject,
                            referencingObjectFieldName,
                            referencingObjectFieldValue,
                            containingSnapshot) {
        if (!referencingObjectFieldValue)
          return;

        if (referencingObjectFieldValue instanceof
            tracing.trace_model.ObjectSnapshot)
          return null;
        if (referencingObjectFieldValue.id === undefined)
          return;

        var implicitSnapshot = referencingObjectFieldValue;

        var rawId = implicitSnapshot.id;
        var m = /(.+)\/(.+)/.exec(rawId);
        if (!m)
          throw new Error('Implicit snapshots must have names.');
        delete implicitSnapshot.id;
        var name = m[1];
        var id = m[2];
        var res;

        var cat;
        if (implicitSnapshot.cat !== undefined)
          cat = implicitSnapshot.cat;
        else
          cat = containingSnapshot.objectInstance.category;

        var baseTypename;
        if (implicitSnapshot.base_type)
          baseTypename = implicitSnapshot.base_type;
        else
          baseTypename = undefined;

        try {
          res = process.objects.addSnapshot(
              id, cat,
              name, containingSnapshot.ts,
              implicitSnapshot, baseTypename);
        } catch (e) {
          this.model_.importWarning({
            type: 'object_snapshot_parse_error',
            message: 'While processing implicit snapshot of ' +
                rawId + ' at ts=' + containingSnapshot.ts + ': ' + e
          });
          return;
        }
        res.objectInstance.hasImplicitSnapshots = true;
        res.containingSnapshot = containingSnapshot;
        referencingObject[referencingObjectFieldName] = res;
        if (!(res instanceof tracing.trace_model.ObjectSnapshot))
          throw new Error('Created object must be instanceof snapshot');
        return res.args;
      }

      /**
       * Iterates over the fields in the object, calling func for every
       * field/value found.
       *
       * @return {object} If the function does not want the field's value to be
       * iterated, return null. If iteration of the field value is desired, then
       * return either undefined (if the field value did not change) or the new
       * field value if it was changed.
       */
      function iterObject(object, func, containingSnapshot, thisArg) {
        if (!(object instanceof Object))
          return;

        if (object instanceof Array) {
          for (var i = 0; i < object.length; i++) {
            var res = func.call(thisArg, object, i, object[i],
                                containingSnapshot);
            if (res === null)
              continue;
            if (res)
              iterObject(res, func, containingSnapshot, thisArg);
            else
              iterObject(object[i], func, containingSnapshot, thisArg);
          }
          return;
        }

        for (var key in object) {
          var res = func.call(thisArg, object, key, object[key],
                              containingSnapshot);
          if (res === null)
            continue;
          if (res)
            iterObject(res, func, containingSnapshot, thisArg);
          else
            iterObject(object[key], func, containingSnapshot, thisArg);
        }
      }

      // TODO(nduca): We may need to iterate the instances in sorted order by
      // creationTs.
      process.objects.iterObjectInstances(function(instance) {
        instance.snapshots.forEach(function(snapshot) {
          if (snapshot.args.id !== undefined)
            throw new Error('args cannot have an id field inside it');
          iterObject(snapshot.args, processField, snapshot, this);
        }, this);
      }, this);
    },

    joinObjectRefs_: function() {
      tvcm.iterItems(this.model_.processes, function(pid, process) {
        this.joinObjectRefsForProcess_(process);
      }, this);
    },

    joinObjectRefsForProcess_: function(process) {
      // Iterate the world, looking for id_refs
      var patchupsToApply = [];
      tvcm.iterItems(process.threads, function(tid, thread) {
        thread.asyncSliceGroup.slices.forEach(function(item) {
          this.searchItemForIDRefs_(
              patchupsToApply, process.objects, 'start', item);
        }, this);
        thread.sliceGroup.slices.forEach(function(item) {
          this.searchItemForIDRefs_(
              patchupsToApply, process.objects, 'start', item);
        }, this);
      }, this);
      process.objects.iterObjectInstances(function(instance) {
        instance.snapshots.forEach(function(item) {
          this.searchItemForIDRefs_(
              patchupsToApply, process.objects, 'ts', item);
        }, this);
      }, this);

      // Change all the fields pointing at id_refs to their real values.
      patchupsToApply.forEach(function(patchup) {
        patchup.object[patchup.field] = patchup.value;
      });
    },

    searchItemForIDRefs_: function(patchupsToApply, objectCollection,
                                   itemTimestampField, item) {
      if (!item.args)
        throw new Error('item is missing its args');

      function handleField(object, fieldName, fieldValue) {
        if (fieldValue === undefined ||
            (!fieldValue.id_ref && !fieldValue.idRef))
          return;

        var id = fieldValue.id_ref || fieldValue.idRef;
        var ts = item[itemTimestampField];
        var snapshot = objectCollection.getSnapshotAt(id, ts);
        if (!snapshot)
          return;

        // We have to delay the actual change to the new value until after all
        // refs have been located. Otherwise, we could end up recursing in
        // ways we definitely didn't intend.
        patchupsToApply.push({object: object,
          field: fieldName,
          value: snapshot});
      }
      function iterObjectFieldsRecursively(object) {
        if (!(object instanceof Object))
          return;

        if ((object instanceof tracing.trace_model.ObjectSnapshot) ||
            (object instanceof Float32Array) ||
            (object instanceof tvcm.Quad))
          return;

        if (object instanceof Array) {
          for (var i = 0; i < object.length; i++) {
            handleField(object, i, object[i]);
            iterObjectFieldsRecursively(object[i]);
          }
          return;
        }

        for (var key in object) {
          var value = object[key];
          handleField(object, key, value);
          iterObjectFieldsRecursively(value);
        }
      }

      iterObjectFieldsRecursively(item.args);
    }
  };

  tracing.TraceModel.registerImporter(TraceEventImporter);

  return {
    TraceEventImporter: TraceEventImporter
  };
});
