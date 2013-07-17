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
      if (ctx === undefined)
        return;

      ctx.save();
      var worldBounds = this.setupCanvasForDraw_();
      this.draw(type, worldBounds.left, worldBounds.right);
      ctx.restore();
    },

    draw: function(type, viewLWorld, viewRWorld) {
    },

    setupCanvasForDraw_: function() {
      var ctx = this.context();
      var pixelRatio = window.devicePixelRatio || 1;
      var bounds = this.getBoundingClientRect();
      var canvasBounds = ctx.canvas.getBoundingClientRect();

      ctx.translate(0, pixelRatio * (bounds.top - canvasBounds.top));

      var viewLWorld = this.viewport.xViewToWorld(0);
      var viewRWorld = this.viewport.xViewToWorld(bounds.width * pixelRatio);

      return {left: viewLWorld, right: viewRWorld};
    },

    /**
     * Called by all the addToSelection functions on the created selection
     * hit objects. Override this function on parent classes to add
     * context-specific information to the hit.
     */
    decorateHit: function(hit) {
    },

    addIntersectingItemsInRangeToSelection: function(
        loVX, hiVX, loVY, hiVY, selection) {

      var pixelRatio = window.devicePixelRatio || 1;
      var viewPixWidthWorld = this.viewport.xViewVectorToWorld(1);
      var loWX = this.viewport.xViewToWorld(loVX * pixelRatio);
      var hiWX = this.viewport.xViewToWorld(hiVX * pixelRatio);

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

    drawInstantEvents_: function(instantEvents, viewLWorld, viewRWorld) {
      var ctx = this.context();
      var pixelRatio = window.devicePixelRatio || 1;

      var bounds = this.getBoundingClientRect();
      var height = bounds.height * pixelRatio;

      // Culling parameters.
      var vp = this.viewport;
      var pixWidth = vp.xViewVectorToWorld(1);

      var palette = tracing.getColorPalette();

      // Begin rendering in world space.
      ctx.save();
      vp.applyTransformToCanvas(ctx);

      var tr = new tracing.FastRectRenderer(ctx, 2 * pixWidth, 2 * pixWidth,
                                            palette);
      tr.setYandH(0, height);

      var lowInstantEvent = base.findLowIndexInSortedArray(
          instantEvents,
          function(instantEvent) { return instantEvent.start; },
          viewLWorld);

      for (var i = lowInstantEvent; i < instantEvents.length; ++i) {
        var instantEvent = instantEvents[i];
        var x = instantEvent.start;
        if (x > viewRWorld)
          break;

        // Less than 0.001 causes short events to disappear when zoomed in.
        var w = Math.max(instantEvent.duration, 0.001);
        var colorId = instantEvent.selected ?
            instantEvent.colorId + highlightIdBoost :
            instantEvent.colorId;

        // InstantEvent: draw a triangle.  If zoomed too far, collapse
        // into the FastRectRenderer.
        if (pixWidth > 0.001) {
          tr.fillRect(x, pixWidth, colorId);
        } else {
          ctx.fillStyle = palette[colorId];
          ctx.beginPath();
          ctx.moveTo(x - (4 * pixWidth), height);
          ctx.lineTo(x, 0);
          ctx.lineTo(x + (4 * pixWidth), height);
          ctx.closePath();
          ctx.fill();
        }
      }
      tr.flush();
      ctx.restore();
    }
  };

  return {
    Track: Track
  };
});
