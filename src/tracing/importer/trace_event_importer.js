// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview TraceEventImporter imports TraceEvent-formatted data
 * into the provided model.
 */
base.require('base.quad');
base.require('tracing.trace_model');
base.require('tracing.color_scheme');
base.require('tracing.trace_model.instant_event');
base.require('tracing.trace_model.counter_series');

base.exportTo('tracing.importer', function() {

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
      // out. It will be picked up by extractSubtrace later on.
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

    __proto__: Object.prototype,

    extractSubtrace: function() {
      var tmp = this.systemTraceEvents_;
      this.systemTraceEvents_ = undefined;
      return tmp;
    },

    /**
     * Deep copying is only needed if the trace was given to us as events.
     */
    deepCopyIfNeeded_: function(obj) {
      if (this.eventsWereFromString_)
        return obj;
      return deepCopy(obj);
    },

    /**
     * Helper to process an 'async finish' event, which will close an open slice
     * on a AsyncSliceGroup object.
     */
    processAsyncEvent: function(event) {
      var thread = this.model_.getOrCreateProcess(event.pid).
          getOrCreateThread(event.tid);
      this.allAsyncEvents_.push({
        event: event,
        thread: thread});
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
              tracing.getStringColorId(ctr.name + '.' + seriesName)));
        }

        if (ctr.numSeries === 0) {
          this.model_.importErrors.push('Expected counter ' + event.name +
              ' to have at least one argument to use as a value.');

          // Drop the counter.
          delete ctr.parent.counters[ctr.name];
          return;
        }
      }

      var ts = event.ts / 1000;
      ctr.series.forEach(function(series) {
        var val = event.args[series.name] ? event.args[series.name] : 0;
        series.addSample(ts, val);
      });
    },

    processObjectEvent: function(event) {
      var thread = this.model_.getOrCreateProcess(event.pid).
          getOrCreateThread(event.tid);
      this.allObjectEvents_.push({
        event: event,
        thread: thread});
    },

    processDurationEvent: function(event) {
      var thread = this.model_.getOrCreateProcess(event.pid)
        .getOrCreateThread(event.tid);
      if (!thread.sliceGroup.isTimestampValidForBeginOrEnd(event.ts / 1000)) {
        this.model_.importErrors.push(
            'Timestamps are moving backward.');
        return;
      }

      if (event.ph == 'B') {
        thread.sliceGroup.beginSlice(event.cat, event.name, event.ts / 1000,
                                     this.deepCopyIfNeeded_(event.args));
      } else {
        if (!thread.sliceGroup.openSliceCount) {
          this.model_.importErrors.push(
              'E phase event without a matching B phase event.');
          return;
        }

        var slice = thread.sliceGroup.endSlice(event.ts / 1000);
        for (var arg in event.args) {
          if (slice.args[arg] !== undefined) {
            this.model_.importErrors.push(
                'Both the B and E phases of ' + slice.name +
                'provided values for argument ' + arg + '. ' +
                'The value of the E phase event will be used.');
          }
          slice.args[arg] = this.deepCopyIfNeeded_(event.args[arg]);
        }
      }
    },

    processMetadataEvent: function(event) {
      if (event.name == 'process_name') {
        var process = this.model_.getOrCreateProcess(event.pid);
        process.name = event.args.name;
      } else if (event.name == 'process_labels') {
        var process = this.model_.getOrCreateProcess(event.pid);
        process.labels.push.apply(
            process.labels, event.args.labels.split(','));
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
        this.model_.importErrors.push(
            'Unrecognized metadata name: ' + event.name);
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

      var colorId = tracing.getStringColorId(event.name);
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

        } else if (event.ph === 'S' || event.ph === 'F' || event.ph === 'T') {
          this.processAsyncEvent(event);

        // Note, I is historic. The instant event marker got changed, but we
        // want to support loading load trace files so we have both I and i.
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
          // NB: toss flow events until there's proper support

        } else {
          this.model_.importErrors.push('Unrecognized event phase: ' +
              event.ph + ' (' + event.name + ')');
        }
      }
    },

    /**
     * Called by the Model after all other importers have imported their
     * events.
     */
    finalizeImport: function() {
      this.createAsyncSlices_();
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
            var slice = new tracing.trace_model.AsyncSlice(
                events[0].event.cat,
                name,
                tracing.getStringColorId(name),
                events[0].event.ts / 1000);

            slice.duration = (event.ts / 1000) - (events[0].event.ts / 1000);

            slice.startThread = events[0].thread;
            slice.endThread = asyncEventState.thread;
            slice.id = id;
            slice.args = this.deepCopyIfNeeded_(events[0].event.args);
            slice.subSlices = [];

            // Create subSlices for each step.
            for (var j = 1; j < events.length; ++j) {
              var subName = name;
              if (events[j - 1].event.ph == 'T')
                subName = name + ':' + events[j - 1].event.args.step;
              var subSlice = new tracing.trace_model.AsyncSlice(
                  events[0].event.cat,
                  subName,
                  tracing.getStringColorId(name + j),
                  events[j - 1].event.ts / 1000);

              subSlice.duration =
                  (events[j].event.ts / 1000) - (events[j - 1].event.ts / 1000);

              subSlice.startThread = events[j - 1].thread;
              subSlice.endThread = events[j].thread;
              subSlice.id = id;
              subSlice.args = this.deepCopyIfNeeded_(events[j - 1].event.args);

              slice.subSlices.push(subSlice);
            }

            // The args for the finish event go in the last subSlice.
            var lastSlice = slice.subSlices[slice.subSlices.length - 1];
            for (var arg in event.args)
              lastSlice.args[arg] = this.deepCopyIfNeeded_(event.args[arg]);

            // Add |slice| to the start-thread's asyncSlices.
            slice.startThread.asyncSliceGroup.push(slice);
            delete asyncEventStatesByNameThenID[name][id];
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
          this.model_.importErrors.push(
              'While processing ' + JSON.stringify(event) + ': ' +
              'Object events require an name parameter.');
        }

        if (event.id === undefined) {
          this.model_.importErrors.push(
              'While processing ' + JSON.stringify(event) + ': ' +
              'Object events require an id parameter.');
        }
        var process = thread.parent;
        var ts = event.ts / 1000;
        var instance;
        if (event.ph == 'N') {
          try {
            instance = process.objects.idWasCreated(
                event.id, event.cat, event.name, ts);
          } catch (e) {
            this.model_.importErrors.push(
                'While processing create of ' +
                event.id + ' at ts=' + ts + ': ' + e);
            return;
          }
        } else if (event.ph == 'O') {
          if (event.args.snapshot === undefined) {
            this.model_.importErrors.push(
                'While processing ' + event.id + ' at ts=' + ts + ': ' +
                'Snapshots must have args: {snapshot: ...}');
            return;
          }
          var snapshot;
          try {
            snapshot = process.objects.addSnapshot(
                event.id, event.cat, event.name, ts,
                this.deepCopyIfNeeded_(event.args.snapshot));
          } catch (e) {
            this.model_.importErrors.push(
                'While processing snapshot of ' +
                event.id + ' at ts=' + ts + ': ' + e);
            return;
          }
          instance = snapshot.objectInstance;
        } else if (event.ph == 'D') {
          try {
            instance = process.objects.idWasDeleted(
                event.id, event.cat, event.name, ts);
          } catch (e) {
            this.model_.importErrors.push(
                'While processing delete of ' +
                event.id + ' at ts=' + ts + ': ' + e);
            return;
          }
        }

        if (instance)
          instance.colorId = tracing.getStringColorId(instance.typeName);
      }

      this.allObjectEvents_.sort(function(x, y) {
        return x.event.ts - y.event.ts;
      });

      var allObjectEvents = this.allObjectEvents_;
      for (var i = 0; i < allObjectEvents.length; i++) {
        var objectEventState = allObjectEvents[i];
        try {
          processEvent.call(this, objectEventState);
        } catch (e) {
          this.model_.importErrors.push(e.message);
        }
      }
    },

    createImplicitObjects_: function() {
      base.iterItems(this.model_.processes, function(pid, process) {
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

        if (referencingObjectFieldValue.id === undefined)
          return;
        if (referencingObjectFieldValue instanceof
            tracing.trace_model.ObjectSnapshot)
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
        try {
          res = process.objects.addSnapshot(
              id, containingSnapshot.objectInstance.category,
              name, containingSnapshot.ts,
              implicitSnapshot);
        } catch (e) {
          this.model_.importErrors.push(
              'While processing implicit snapshot of ' +
              rawId + ' at ts=' + containingSnapshot.ts + ': ' + e);
          return;
        }
        res.objectInstance.hasImplicitSnapshots = true;
        res.containingSnapshot = containingSnapshot;
        referencingObject[referencingObjectFieldName] = res;
        if (!(res instanceof tracing.trace_model.ObjectSnapshot))
          throw new Error('Created object must be instanceof snapshot');
        return res.args;
      }

      function iterObject(object, func, containingSnapshot, thisArg) {
        if (!(object instanceof Object))
          return;

        if (object instanceof Array) {
          for (var i = 0; i < object.length; i++) {
            var res = func.call(thisArg, object, i, object[i],
                                containingSnapshot);
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
      base.iterItems(this.model_.processes, function(pid, process) {
        this.joinObjectRefsForProcess_(process);
      }, this);
    },

    joinObjectRefsForProcess_: function(process) {
      // Iterate the world, looking for id_refs
      var patchupsToApply = [];
      base.iterItems(process.threads, function(tid, thread) {
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
        throw new Error('');

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
            (object instanceof base.Quad))
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
