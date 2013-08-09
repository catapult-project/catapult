// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracing.tracks.slice_track');

base.require('base.sorted_array_utils');
base.require('tracing.tracks.heading_track');
base.require('tracing.fast_rect_renderer');
base.require('tracing.color_scheme');
base.require('tracing.draw_helpers');
base.require('ui');

base.exportTo('tracing.tracks', function() {

  var palette = tracing.getColorPalette();

  /**
   * A track that displays an array of Slice objects.
   * @constructor
   * @extends {HeadingTrack}
   */

  var SliceTrack = ui.define(
      'slice-track', tracing.tracks.HeadingTrack);

  SliceTrack.prototype = {

    __proto__: tracing.tracks.HeadingTrack.prototype,

    decorate: function(viewport) {
      tracing.tracks.HeadingTrack.prototype.decorate.call(this, viewport);
      this.classList.add('slice-track');
      this.asyncStyle_ = false;
      this.slices_ = null;
    },

    get asyncStyle() {
      return this.asyncStyle_;
    },

    set asyncStyle(v) {
      this.asyncStyle_ = !!v;
    },

    get slices() {
      return this.slices_;
    },

    set slices(slices) {
      this.slices_ = slices || [];
    },

    get height() {
      return window.getComputedStyle(this).height;
    },

    set height(height) {
      this.style.height = height;
    },

    get hasVisibleContent() {
      return this.slices.length > 0;
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

      ctx.save();
      if (this.asyncStyle_)
        ctx.globalAlpha = 0.25;

      var bounds = this.getBoundingClientRect();
      tracing.drawSlices(
          ctx,
          this.viewport.currentDisplayTransform,
          viewLWorld,
          viewRWorld,
          bounds.height,
          this.slices_);
      ctx.restore();

      if (bounds.height <= 8)
        return;

      tracing.drawLabels(
          ctx,
          this.viewport.currentDisplayTransform,
          viewLWorld,
          viewRWorld,
          this.slices_);
    },

    memoizeSlices_: function() {
      if (this.slices_ === undefined || this.slices_ === null)
        return;

      var vp = this.viewport_;
      this.slices_.forEach(function(slice) {
        vp.sliceMemoization(slice, this);
      }.bind(this));
    },

    addIntersectingItemsInRangeToSelectionInWorldSpace: function(
        loWX, hiWX, viewPixWidthWorld, selection) {
      function onPickHit(slice) {
        var hit = selection.addSlice(this, slice);
        this.decorateHit(hit);
      }
      base.iterateOverIntersectingIntervals(this.slices_,
          function(x) { return x.start; },
          function(x) { return x.duration; },
          loWX, hiWX,
          onPickHit.bind(this));
    },

    /**
     * Find the index for the given slice.
     * @return {index} Index of the given slice, or undefined.
     * @private
     */
    indexOfSlice_: function(slice) {
      var index = base.findLowIndexInSortedArray(this.slices_,
          function(x) { return x.start; },
          slice.start);
      while (index < this.slices_.length &&
          slice.start == this.slices_[index].start &&
          slice.colorId != this.slices_[index].colorId) {
        index++;
      }
      return index < this.slices_.length ? index : undefined;
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
      if (!hit.slice)
        return false;

      var index = this.indexOfSlice_(hit.slice);
      if (index === undefined)
        return false;

      var newIndex = index + offset;
      if (newIndex < 0 || newIndex >= this.slices_.length)
        return false;

      var hit = selection.addSlice(this, this.slices_[newIndex]);
      this.decorateHit(hit);
      return true;
    },

    addAllObjectsMatchingFilterToSelection: function(filter, selection) {
      for (var i = 0; i < this.slices_.length; ++i) {
        if (filter.matchSlice(this.slices_[i])) {
          var hit = selection.addSlice(this, this.slices_[i]);
          this.decorateHit(hit);
        }
      }
    }
  };

  return {
    SliceTrack: SliceTrack
  };
});
