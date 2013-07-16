// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Code for the viewport.
 */
base.require('base.events');
base.require('base.guid');
base.require('base.range');

base.exportTo('tracing', function() {

  function SelectionSliceHit(track, slice) {
    this.track = track;
    this.slice = slice;
  }
  SelectionSliceHit.prototype = {
    get modelObject() {
      return this.slice;
    },

    get selected() {
      return this.slice.selected;
    },
    set selected(v) {
      this.slice.selected = v;
    },
    addBoundsToRange: function(range) {
      range.addValue(this.slice.start);
      range.addValue(this.slice.end);
    }
  };

  function SelectionCounterSampleHit(track, counter, sampleIndex) {
    this.track = track;
    this.counter = counter;
    this.sampleIndex = sampleIndex;
  }

  SelectionCounterSampleHit.prototype = {
    get modelObject() {
      return this.sampleIndex;
    },

    get selected() {
      return this.track.selectedSamples[this.sampleIndex] == true;
    },

    set selected(v) {
      if (v)
        this.track.selectedSamples[this.sampleIndex] = true;
      else
        this.track.selectedSamples[this.sampleIndex] = false;
    },

    addBoundsToRange: function(range) {
      if (!this.track.timestamps)
        return;
      range.addValue(this.track.timestamps[this.sampleIndex]);
    }
  };

  function SelectionObjectSnapshotHit(track, objectSnapshot) {
    this.track = track;
    this.objectSnapshot = objectSnapshot;
  }
  SelectionObjectSnapshotHit.prototype = {
    get modelObject() {
      return this.objectSnapshot;
    },

    get selected() {
      return this.objectSnapshot.selected;
    },
    set selected(v) {
      this.objectSnapshot.selected = v;
    },
    addBoundsToRange: function(range) {
      range.addValue(this.objectSnapshot.ts);
    }
  };

  function SelectionObjectInstanceHit(track, objectInstance) {
    this.track = track;
    this.objectInstance = objectInstance;
  }
  SelectionObjectInstanceHit.prototype = {
    get modelObject() {
      return this.objectInstance;
    },

    get selected() {
      return this.objectInstance.selected;
    },
    set selected(v) {
      this.objectInstance.selected = v;
    },
    addBoundsToRange: function(range) {
      range.addRange(this.objectInstance.bounds);
    }
  };

  var HIT_TYPES = [
    {
      constructor: SelectionSliceHit,
      name: 'slice',
      pluralName: 'slices'
    },
    {
      constructor: SelectionCounterSampleHit,
      name: 'counterSample',
      pluralName: 'counterSamples'
    },
    {
      constructor: SelectionObjectSnapshotHit,
      name: 'objectSnapshot',
      pluralName: 'objectSnapshots'
    },
    {
      constructor: SelectionObjectInstanceHit,
      name: 'objectInstance',
      pluralName: 'objectInstances'
    }
  ];

  /**
   * Represents a selection within a  and its associated set of tracks.
   * @constructor
   */
  function Selection(opt_hits) {
    this.bounds_dirty_ = true;
    this.bounds_ = new base.Range();
    this.length_ = 0;
    this.guid_ = base.GUID.allocate();

    if (opt_hits)
      this.pushHits(opt_hits);
  }
  Selection.prototype = {
    __proto__: Object.prototype,

    get bounds() {
      if (this.bounds_dirty_) {
        this.bounds_.reset();
        for (var i = 0; i < this.length_; i++) {
          var hit = this[i];
          hit.addBoundsToRange(this.bounds_);
        }
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

    pushHit: function(hit) {
      this.push_(hit);
    },

    pushHits: function(hits) {
      for (var i = 0; i < hits.length; i++)
        this.pushHit(hits[i]);
    },

    push_: function(hit) {
      this[this.length_++] = hit;
      this.bounds_dirty_ = true;
      return hit;
    },

    addSlice: function(track, slice) {
      return this.push_(new SelectionSliceHit(track, slice));
    },

    addCounterSample: function(track, counter, sampleIndex) {
      return this.push_(
          new SelectionCounterSampleHit(
          track, counter, sampleIndex));
    },

    addObjectSnapshot: function(track, objectSnapshot) {
      return this.push_(
          new SelectionObjectSnapshotHit(track, objectSnapshot));
    },

    addObjectInstance: function(track, objectInstance) {
      return this.push_(
          new SelectionObjectInstanceHit(track, objectInstance));
    },

    addSelection: function(selection) {
      for (var i = 0; i < selection.length; i++)
        this.push_(selection[i]);
    },

    subSelection: function(index, count) {
      count = count || 1;

      var selection = new Selection();
      selection.bounds_dirty_ = true;
      if (index < 0 || index + count > this.length_)
        throw new Error('Index out of bounds');

      for (var i = index; i < index + count; i++)
        selection.push_(this[i]);

      return selection;
    },

    getCounterSampleHitsAsSelection: function() {
      var selection = new Selection();
      this.enumHitsOfType(SelectionCounterSampleHit,
                          selection.push_.bind(selection));
      return selection;
    },

    getSliceHitsAsSelection: function() {
      var selection = new Selection();
      this.enumHitsOfType(SelectionSliceHit,
                          selection.push_.bind(selection));
      return selection;
    },

    getHitsOrganizedByType: function() {
      var hits = {};
      HIT_TYPES.forEach(function(hitType) {
        hits[hitType.pluralName] = new Selection();
      });
      for (var i = 0; i < this.length_; i++) {
        var hit = this[i];
        HIT_TYPES.forEach(function(hitType) {
          if (hit instanceof hitType.constructor)
            hits[hitType.pluralName].push_(hit);
        });
      }
      return hits;
    },

    enumHitsOfType: function(type, func) {
      for (var i = 0; i < this.length_; i++)
        if (this[i] instanceof type)
          func(this[i]);
    },

    getNumSliceHits: function() {
      var numHits = 0;
      this.enumHitsOfType(SelectionSliceHit, function(hit) { numHits++; });
      return numHits;
    },

    getNumCounterHits: function() {
      var numHits = 0;
      this.enumHitsOfType(SelectionCounterSampleHit, function(hit) {
        numHits++;
      });
      return numHits;
    },

    getNumObjectSnapshotHits: function() {
      var numHits = 0;
      this.enumHitsOfType(SelectionObjectSnapshotHit, function(hit) {
        numHits++;
      });
      return numHits;
    },

    getNumObjectInstanceHits: function() {
      var numHits = 0;
      this.enumHitsOfType(SelectionObjectInstanceHit, function(hit) {
        numHits++;
      });
      return numHits;
    },

    map: function(fn) {
      for (var i = 0; i < this.length_; i++)
        fn(this[i]);
    },

    /**
     * Helper for selection previous or next.
     * @param {boolean} forwardp If true, select one forward (next).
     *   Else, select previous.
     * @return {boolean} true if current selection changed.
     */
    getShiftedSelection: function(offset) {
      var newSelection = new Selection();
      for (var i = 0; i < this.length_; i++) {
        var hit = this[i];
        hit.track.addItemNearToProvidedHitToSelection(
            hit, offset, newSelection);
      }

      if (newSelection.length == 0)
        return undefined;
      return newSelection;
    }
  };

  function createSelectionFromObjectAndView(obj, opt_view) {
    // TODO: fill in the track intelligently by finding the TimelineView, then
    // finding the right track based on the provided object.
    var track = undefined;

    var selection = new Selection();
    if (obj instanceof tracing.trace_model.Slice)
      selection.addSlice(track, obj);
    else if (obj instanceof tracing.trace_model.ObjectSnapshot)
      selection.addObjectSnapshot(track, obj);
    else if (obj instanceof tracing.trace_model.ObjectInstance)
      selection.addObjectInstance(track, obj);
    else
      throw new Error('Unrecognized selection type');
    return selection;
  }

  return {
    SelectionSliceHit: SelectionSliceHit,
    SelectionCounterSampleHit: SelectionCounterSampleHit,
    SelectionObjectSnapshotHit: SelectionObjectSnapshotHit,
    SelectionObjectInstanceHit: SelectionObjectInstanceHit,
    Selection: Selection,
    createSelectionFromObjectAndView: createSelectionFromObjectAndView
  };
});
