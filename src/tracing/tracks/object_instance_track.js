// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracing.tracks.object_instance_track');

base.require('base.sorted_array_utils');
base.require('tracing.tracks.canvas_based_track');
base.require('tracing.color_scheme');
base.require('ui');

base.exportTo('tracing.tracks', function() {

  var palette = tracing.getColorPalette();
  var highlightIdBoost = tracing.getColorPaletteHighlightIdBoost();

  /**
   * A track that displays an array of Slice objects.
   * @constructor
   * @extends {CanvasBasedTrack}
   */

  var ObjectInstanceTrack = ui.define(
      'object-instance-track', tracing.tracks.CanvasBasedTrack);

  ObjectInstanceTrack.prototype = {

    __proto__: tracing.tracks.CanvasBasedTrack.prototype,

    decorate: function() {
      this.classList.add('object-instance-track');
      this.objectInstances_ = [];
      this.objectSnapshots_ = [];
    },

    get objectInstances() {
      return this.objectInstances_;
    },

    set objectInstances(objectInstances) {
      this.invalidate();
      if (!objectInstances) {
        this.objectInstances_ = [];
        this.objectSnapshots_ = [];
        this.objectSnapshots_ = [];
        this.visible = false;
        return;
      }
      this.visible = true;
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
      this.invalidate();
    },

    get snapshotRadiusView() {
      return 7 * (window.devicePixelRatio || 1);
    },

    redraw: function() {
      var ctx = this.ctx_;
      var canvasW = this.canvas_.width;
      var canvasH = this.canvas_.height;
      var halfCanvasH = canvasH * 0.5;
      var twoPi = Math.PI * 2;
      var pixelRatio = window.devicePixelRatio || 1;

      ctx.clearRect(0, 0, canvasW, canvasH);

      // Culling parameters.
      var vp = this.viewport_;
      var pixWidthWorld = vp.xViewVectorToWorld(1);
      var viewLWorld = vp.xViewToWorld(0);
      var viewRWorld = vp.xViewToWorld(canvasW);
      var snapshotRadiusView = this.snapshotRadiusView;
      var snapshotRadiusWorld = vp.xViewVectorToWorld(canvasH);
      var loI;

      // Give the viewport a chance to draw onto this canvas.
      vp.drawUnderContent(ctx, viewLWorld, viewRWorld, canvasH);

      // Begin rendering in world space.
      ctx.save();
      vp.applyTransformToCanvas(ctx);

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
        ctx.fillRect(x, pixelRatio, right - x, canvasH - 2 * pixelRatio);
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
        var xView = vp.xWorldToView(x);

        var colorId = snapshot.selected ?
            snapshot.objectInstance.colorId + highlightIdBoost :
            snapshot.objectInstance.colorId;

        ctx.fillStyle = palette[colorId];
        ctx.beginPath();
        ctx.arc(xView, halfCanvasH, snapshotRadiusView, 0, twoPi);
        ctx.fill();
        if (snapshot.selected) {
          ctx.lineWidth = 5;
          ctx.strokeStyle = 'rgb(100,100,0)';
          ctx.stroke();

          ctx.beginPath();
          ctx.arc(xView, halfCanvasH, snapshotRadiusView - 1, 0, twoPi);
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

      // Give the viewport a chance to draw over this canvas.
      vp.drawOverContent(ctx, viewLWorld, viewRWorld, canvasH);
    },

    addIntersectingItemsInRangeToSelectionInWorldSpace: function(
        loWX, hiWX, viewPixWidthWorld, selection) {
      var that = this;

      // Pick snapshots first.
      var foundSnapshot = false;
      function onSnapshotHit(snapshot) {
        selection.addObjectSnapshot(that, snapshot);
        foundSnapshot = true;
      }
      var snapshotRadiusView = this.snapshotRadiusView;
      var snapshotRadiusWorld = viewPixWidthWorld * snapshotRadiusView;
      base.iterateOverIntersectingIntervals(
          this.objectSnapshots_,
          function(x) { return x.ts - snapshotRadiusWorld; },
          function(x) { return 2 * snapshotRadiusWorld; },
          loWX, hiWX,
          onSnapshotHit);
      if (foundSnapshot)
        return;

      // Try picking instances.
      function onInstanceHit(instance) {
        selection.addObjectInstance(that, instance);
      }
      base.iterateOverIntersectingIntervals(
          this.objectInstances_,
          function(x) { return x.creationTs; },
          function(x) { return x.deletionTs - x.creationTs; },
          loWX, hiWX,
          onInstanceHit);
    },

    /**
     * Add the item to the left or right of the provided hit, if any, to the
     * selection.
     * @param {slice} The current slice.
     * @param {Number} offset Number of slices away from the hit to look.
     * @param {Selection} selection The selection to add a hit to,
     * if found.
     * @return {boolean} Whether a hit was found.
     * @private
     */
    addItemNearToProvidedHitToSelection: function(hit, offset, selection) {
      if (hit instanceof tracing.SelectionObjectSnapshotHit) {
        var index = this.objectSnapshots_.indexOf(hit.objectSnapshot);
        var newIndex = index + offset;
        if (newIndex >= 0 && newIndex < this.objectSnapshots_.length) {
          selection.addObjectSnapshot(this, this.objectSnapshots_[newIndex]);
          return true;
        }
      } else if (hit instanceof tracing.SelectionObjectInstanceHit) {
        var index = this.objectInstances_.indexOf(hit.objectInstance);
        var newIndex = index + offset;
        if (newIndex >= 0 && newIndex < this.objectInstances_.length) {
          selection.addObjectInstance(this, this.objectInstances_[newIndex]);
          return true;
        }
      } else {
        throw new Error('Unrecognized hit');
      }
      return false;
    },

    addAllObjectsMatchingFilterToSelection: function(filter, selection) {
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
