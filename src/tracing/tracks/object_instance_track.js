// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracing.tracks.object_instance_track');

base.require('base.sorted_array_utils');
base.require('tracing.tracks.heading_track');
base.require('tracing.color_scheme');
base.require('ui');

base.exportTo('tracing.tracks', function() {

  var palette = tracing.getColorPalette();
  var highlightIdBoost = tracing.getColorPaletteHighlightIdBoost();

  /**
   * A track that displays an array of Slice objects.
   * @constructor
   * @extends {HeadingTrack}
   */

  var ObjectInstanceTrack = ui.define(
      'object-instance-track', tracing.tracks.HeadingTrack);

  ObjectInstanceTrack.prototype = {
    __proto__: tracing.tracks.HeadingTrack.prototype,

    decorate: function(viewport) {
      tracing.tracks.HeadingTrack.prototype.decorate.call(this, viewport);
      this.classList.add('object-instance-track');
      this.objectInstances_ = [];
      this.objectSnapshots_ = [];
    },

    get objectInstances() {
      return this.objectInstances_;
    },

    set objectInstances(objectInstances) {
      if (!objectInstances || objectInstances.length == 0) {
        this.heading = '';
        this.objectInstances_ = [];
        this.objectSnapshots_ = [];
        return;
      }
      this.heading = objectInstances[0].typeName;
      this.objectInstances_ = objectInstances;
      this.objectSnapshots_ = [];
      this.objectInstances_.forEach(function(instance) {
        this.objectSnapshots_.push.apply(
            this.objectSnapshots_, instance.snapshots);
      }, this);
    },

    get height() {
      return window.getComputedStyle(this).height;
    },

    set height(height) {
      this.style.height = height;
    },

    get snapshotRadiusView() {
      return 7 * (window.devicePixelRatio || 1);
    },

    draw: function(type, viewLWorld, viewRWorld) {
      switch (type) {
        case tracing.tracks.DrawType.SLICE:
          this.drawSlices_(viewLWorld, viewRWorld);
          break;
      }
    },

    drawSlices_: function(viewLWorld, viewRWorld) {
      var ctx = this.context();
      var pixelRatio = window.devicePixelRatio || 1;

      var bounds = this.getBoundingClientRect();
      var height = bounds.height * pixelRatio;
      var halfHeight = height * 0.5;
      var twoPi = Math.PI * 2;

      // Culling parameters.
      var dt = this.viewport.currentDisplayTransform;
      var snapshotRadiusView = this.snapshotRadiusView;
      var snapshotRadiusWorld = dt.xViewVectorToWorld(height);
      var loI;

      // Begin rendering in world space.
      ctx.save();
      dt.applyTransformToCanvas(ctx);

      // Instances
      var objectInstances = this.objectInstances_;
      var loI = base.findLowIndexInSortedArray(
          objectInstances,
          function(instance) {
            return instance.deletionTs;
          },
          viewLWorld);
      ctx.globalAlpha = 0.25;
      ctx.strokeStyle = 'rgb(0,0,0)';
      for (var i = loI; i < objectInstances.length; ++i) {
        var instance = objectInstances[i];
        var x = instance.creationTs;
        if (x > viewRWorld)
          break;

        var colorId = instance.selected ?
            instance.colorId + highlightIdBoost :
            instance.colorId;

        var right = instance.deletionTs == Number.MAX_VALUE ?
            viewRWorld : instance.deletionTs;
        ctx.fillStyle = palette[colorId];
        ctx.fillRect(x, pixelRatio, right - x, height - 2 * pixelRatio);
      }
      ctx.globalAlpha = 1;
      ctx.restore();

      // Snapshots. Has to run in worldspace because ctx.arc gets transformed.
      var objectSnapshots = this.objectSnapshots_;
      loI = base.findLowIndexInSortedArray(
          objectSnapshots,
          function(snapshot) {
            return snapshot.ts +
                snapshotRadiusWorld;
          },
          viewLWorld);
      for (var i = loI; i < objectSnapshots.length; ++i) {
        var snapshot = objectSnapshots[i];
        var x = snapshot.ts;
        if (x - snapshotRadiusWorld > viewRWorld)
          break;
        var xView = dt.xWorldToView(x);

        var colorId = snapshot.selected ?
            snapshot.objectInstance.colorId + highlightIdBoost :
            snapshot.objectInstance.colorId;

        ctx.fillStyle = palette[colorId];
        ctx.beginPath();
        ctx.arc(xView, halfHeight, snapshotRadiusView, 0, twoPi);
        ctx.fill();
        if (snapshot.selected) {
          ctx.lineWidth = 5;
          ctx.strokeStyle = 'rgb(100,100,0)';
          ctx.stroke();

          ctx.beginPath();
          ctx.arc(xView, halfHeight, snapshotRadiusView - 1, 0, twoPi);
          ctx.lineWidth = 2;
          ctx.strokeStyle = 'rgb(255,255,0)';
          ctx.stroke();
        } else {
          ctx.lineWidth = 1;
          ctx.strokeStyle = 'rgb(0,0,0)';
          ctx.stroke();
        }
      }
      ctx.lineWidth = 1;
    },

    addEventsToTrackMap: function(eventToTrackMap) {
      if (this.objectInstance_ !== undefined) {
        this.objectInstance_.forEach(function(obj) {
          eventToTrackMap.addEvent(obj, this);
        }, this);
      }

      if (this.objectSnapshots_ !== undefined) {
        this.objectSnapshots_.forEach(function(obj) {
          eventToTrackMap.addEvent(obj, this);
        }, this);
      }
    },

    addIntersectingItemsInRangeToSelectionInWorldSpace: function(
        loWX, hiWX, viewPixWidthWorld, selection) {
      // Pick snapshots first.
      var foundSnapshot = false;
      function onSnapshot(snapshot) {
        selection.push(snapshot);
        foundSnapshot = true;
      }
      var snapshotRadiusView = this.snapshotRadiusView;
      var snapshotRadiusWorld = viewPixWidthWorld * snapshotRadiusView;
      base.iterateOverIntersectingIntervals(
          this.objectSnapshots_,
          function(x) { return x.ts - snapshotRadiusWorld; },
          function(x) { return 2 * snapshotRadiusWorld; },
          loWX, hiWX,
          onSnapshot);
      if (foundSnapshot)
        return;

      // Try picking instances.
      base.iterateOverIntersectingIntervals(
          this.objectInstances_,
          function(x) { return x.creationTs; },
          function(x) { return x.deletionTs - x.creationTs; },
          loWX, hiWX,
          selection.push.bind(selection));
    },

    /**
     * Add the item to the left or right of the provided event, if any, to the
     * selection.
     * @param {event} The current event item.
     * @param {Number} offset Number of slices away from the event to look.
     * @param {Selection} selection The selection to add an event to,
     * if found.
     * @return {boolean} Whether an event was found.
     * @private
     */
    addItemNearToProvidedEventToSelection: function(event, offset, selection) {
      var events;
      if (event instanceof tracing.trace_model.ObjectSnapshot)
        events = this.objectSnapshots_;
      else if (event instanceof tracing.trace_model.ObjectInstance)
        events = this.objectInstances_;
      else
        throw new Error('Unrecognized event');

      var index = events.indexOf(event);
      var newIndex = index + offset;
      if (newIndex >= 0 && newIndex < events.length) {
        selection.push(events[newIndex]);
        return true;
      }
      return false;
    },

    addAllObjectsMatchingFilterToSelection: function(filter, selection) {
    },

    addClosestEventToSelection: function(worldX, worldMaxDist, loY, hiY,
                                         selection) {
      var snapshot = base.findClosestElementInSortedArray(
          this.objectSnapshots_,
          function(x) { return x.ts; },
          worldX,
          worldMaxDist);

      if (!snapshot)
        return;

      selection.push(snapshot);

      // TODO(egraether): Search for object instances as well, which was not
      // implemented because it makes little sense with the current visual and
      // needs to take care of overlapping intervals.
    }
  };

  ObjectInstanceTrack.typeNameToTrackConstructorMap = {};
  ObjectInstanceTrack.register = function(typeName, constructor) {
    if (ObjectInstanceTrack.typeNameToTrackConstructorMap[typeName])
      throw new Error('Handler already registered for ' + typeName);
    ObjectInstanceTrack.typeNameToTrackConstructorMap[typeName] =
        constructor;
  };

  ObjectInstanceTrack.getTrackConstructor = function(typeName) {
    return ObjectInstanceTrack.typeNameToTrackConstructorMap[typeName];
  };

  return {
    ObjectInstanceTrack: ObjectInstanceTrack
  };
});
