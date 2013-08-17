// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Renders an array of slices into the provided div,
 * using a child canvas element. Uses a FastRectRenderer to draw only
 * the visible slices.
 */

base.requireStylesheet('tracing.tracks.track');

base.require('ui');
base.require('ui.container_that_decorates_its_children');
base.require('tracing.color_scheme');

base.exportTo('tracing.tracks', function() {
  var highlightIdBoost = tracing.getColorPaletteHighlightIdBoost();

  /**
   * The base class for all tracks.
   * @constructor
   */
  var Track = ui.define('track', ui.ContainerThatDecoratesItsChildren);
  Track.prototype = {
    __proto__: ui.ContainerThatDecoratesItsChildren.prototype,

    decorate: function(viewport) {
      ui.ContainerThatDecoratesItsChildren.prototype.decorate.call(this);
      if (viewport === undefined)
        throw new Error('viewport is required when creating a Track.');

      this.viewport_ = viewport;
      this.classList.add('track');
      this.categoryFilter_ = undefined;
    },

    get viewport() {
      return this.viewport_;
    },

    context: function() {
      // This is a little weird here, but we have to be able to walk up the
      // parent tree to get the context.
      if (!this.parentNode)
        return undefined;
      if (!this.parentNode.context)
        throw new Error('Parent container does not support context() method.');
      return this.parentNode.context();
    },

    get categoryFilter() {
      return this.categoryFilter_;
    },

    set categoryFilter(categoryFilter) {
      if (this.categoryFilter_ == categoryFilter)
        return;
      this.categoryFilter_ = categoryFilter;
      this.updateContents_();
    },

    decorateChild_: function(childTrack) {
      if (childTrack instanceof Track)
        childTrack.categoryFilter = this.categoryFilter;
    },

    undecorateChild_: function(childTrack) {
      if (childTrack.detach)
        childTrack.detach();
    },

    updateContents_: function() {
    },

    drawTrack: function(type) {
      var ctx = this.context();

      var pixelRatio = window.devicePixelRatio || 1;
      var bounds = this.getBoundingClientRect();
      var canvasBounds = ctx.canvas.getBoundingClientRect();

      ctx.save();
      ctx.translate(0, pixelRatio * (bounds.top - canvasBounds.top));

      var dt = this.viewport.currentDisplayTransform;
      var viewLWorld = dt.xViewToWorld(0);
      var viewRWorld = dt.xViewToWorld(bounds.width * pixelRatio);

      this.draw(type, viewLWorld, viewRWorld);
      ctx.restore();
    },

    draw: function(type, viewLWorld, viewRWorld) {
    },

    addEventsToTrackMap: function(eventToTrackMap) {
    },

    addIntersectingItemsInRangeToSelection: function(
        loVX, hiVX, loVY, hiVY, selection) {

      var pixelRatio = window.devicePixelRatio || 1;
      var dt = this.viewport.currentDisplayTransform;
      var viewPixWidthWorld = dt.xViewVectorToWorld(1);
      var loWX = dt.xViewToWorld(loVX * pixelRatio);
      var hiWX = dt.xViewToWorld(hiVX * pixelRatio);

      var clientRect = this.getBoundingClientRect();
      var a = Math.max(loVY, clientRect.top);
      var b = Math.min(hiVY, clientRect.bottom);
      if (a > b)
        return;

      this.addIntersectingItemsInRangeToSelectionInWorldSpace(
          loWX, hiWX, viewPixWidthWorld, selection);
    },

    addIntersectingItemsInRangeToSelectionInWorldSpace: function(
        loWX, hiWX, viewPixWidthWorld, selection) {
    },

    /**
     * Gets implemented by supporting track types. The method adds the event
     * closest to worldX to the selection.
     *
     * @param {number} worldX The position that is looked for.
     * @param {number} worldMaxDist The maximum distance allowed from worldX to
     *     the event.
     * @param {number} loY Lower Y bound of the search interval in view space.
     * @param {number} hiY Upper Y bound of the search interval in view space.
     * @param {Selection} selection Selection to which to add hits.
     */
    addClosestEventToSelection: function(
        worldX, worldMaxDist, loY, hiY, selection) {
    },

    addClosestInstantEventToSelection: function(instantEvents, worldX,
                                                worldMaxDist, selection) {
      var instantEvent = base.findClosestElementInSortedArray(
          instantEvents,
          function(x) { return x.start; },
          worldX,
          worldMaxDist);

      if (!instantEvent)
        return;

      selection.push(instantEvent);
    }
  };

  return {
    Track: Track
  };
});
