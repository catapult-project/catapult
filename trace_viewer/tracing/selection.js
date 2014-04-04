// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Code for the viewport.
 */
tvcm.require('tvcm.events');
tvcm.require('tvcm.guid');
tvcm.require('tvcm.range');
tvcm.require('tracing.trace_model.instant_event');
tvcm.require('tracing.trace_model.flow_event');
tvcm.require('tracing.trace_model');

tvcm.exportTo('tracing', function() {

  var RequestSelectionChangeEvent = tvcm.Event.bind(
      undefined, 'requestSelectionChange', true, false);

  var EVENT_TYPES = [
    {
      constructor: tracing.trace_model.Slice,
      name: 'slice',
      pluralName: 'slices'
    },
    {
      constructor: tracing.trace_model.InstantEvent,
      name: 'instantEvent',
      pluralName: 'instantEvents'
    },
    {
      constructor: tracing.trace_model.CounterSample,
      name: 'counterSample',
      pluralName: 'counterSamples'
    },
    {
      constructor: tracing.trace_model.ObjectSnapshot,
      name: 'objectSnapshot',
      pluralName: 'objectSnapshots'
    },
    {
      constructor: tracing.trace_model.ObjectInstance,
      name: 'objectInstance',
      pluralName: 'objectInstances'
    },
    {
      constructor: tracing.trace_model.Sample,
      name: 'sample',
      pluralName: 'samples'
    },
    {
      constructor: tracing.trace_model.FlowEvent,
      name: 'flowEvent',
      pluralName: 'flowEvents'
    }
  ];

  /**
   * Represents a selection within a  and its associated set of tracks.
   * @constructor
   */
  function Selection(opt_events) {
    this.bounds_dirty_ = true;
    this.bounds_ = new tvcm.Range();
    this.length_ = 0;
    this.guid_ = tvcm.GUID.allocate();

    if (opt_events) {
      for (var i = 0; i < opt_events.length; i++)
        this.push(opt_events[i]);
    }
  }
  Selection.prototype = {
    __proto__: Object.prototype,

    get bounds() {
      if (this.bounds_dirty_) {
        this.bounds_.reset();
        for (var i = 0; i < this.length_; i++)
          this[i].addBoundsToRange(this.bounds_);
        this.bounds_dirty_ = false;
      }
      return this.bounds_;
    },

    get duration() {
      if (this.bounds_.isEmpty)
        return 0;
      return this.bounds_.max - this.bounds_.min;
    },

    get length() {
      return this.length_;
    },

    get guid() {
      return this.guid_;
    },

    clear: function() {
      for (var i = 0; i < this.length_; ++i)
        delete this[i];
      this.length_ = 0;
      this.bounds_dirty_ = true;
    },

    push: function(event) {
      this[this.length_++] = event;
      this.bounds_dirty_ = true;
      return event;
    },

    addSelection: function(selection) {
      for (var i = 0; i < selection.length; i++)
        this.push(selection[i]);
    },

    subSelection: function(index, count) {
      count = count || 1;

      var selection = new Selection();
      selection.bounds_dirty_ = true;
      if (index < 0 || index + count > this.length_)
        throw new Error('Index out of bounds');

      for (var i = index; i < index + count; i++)
        selection.push(this[i]);

      return selection;
    },

    getEventsOrganizedByType: function() {
      var events = {};
      EVENT_TYPES.forEach(function(eventType) {
        events[eventType.pluralName] = new Selection();
      });
      for (var i = 0; i < this.length_; i++) {
        var event = this[i];
        EVENT_TYPES.forEach(function(eventType) {
          if (event instanceof eventType.constructor)
            events[eventType.pluralName].push(event);
        });
      }
      return events;
    },

    enumEventsOfType: function(type, func) {
      for (var i = 0; i < this.length_; i++)
        if (this[i] instanceof type)
          func(this[i]);
    },

    map: function(fn) {
      for (var i = 0; i < this.length_; i++)
        fn(this[i]);
    },

    /**
     * Helper for selection previous or next.
     * @param {boolean} offset If positive, select one forward (next).
     *   Else, select previous.
     *
     * @param {TimelineViewport} viewport The viewport to use to determine what
     * is near to the current selection.
     *
     * @return {boolean} true if current selection changed.
     */
    getShiftedSelection: function(viewport, offset) {
      var newSelection = new Selection();
      for (var i = 0; i < this.length_; i++) {
        var event = this[i];

        var addEventToNewSelection = function(event) {
        };

        // If this is a flow event, and we have a next/prev item in the chain
        // then we use that as the item to move too. Otherwise, we let the
        // normal movement for a slice kick in and use that.
        if (event instanceof tracing.trace_model.FlowEvent) {
          if ((offset > 0) && event.nextFlowEvent) {
            newSelection.push(event.nextFlowEvent);
            continue;
          } else if ((offset < 0) && event.previousFlowEvent) {
            newSelection.push(event.previousFlowEvent);
            continue;
          }
        }

        var track = viewport.trackForEvent(event);
        track.addItemNearToProvidedEventToSelection(
            event, offset, newSelection);
      }

      if (newSelection.length == 0)
        return undefined;
      return newSelection;
    }
  };

  return {
    Selection: Selection,
    RequestSelectionChangeEvent: RequestSelectionChangeEvent
  };
});
