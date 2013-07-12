// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracing.tracks.drawable_track');
base.requireStylesheet('tracing.tracks.drawing_container');

base.require('base.raf');
base.require('tracing.tracks.track');
base.require('tracing.fast_rect_renderer');
base.require('tracing.color_scheme');
base.require('ui');

base.exportTo('tracing.tracks', function() {
  /**
   * A drawable track constructed. Provides the basic heading and
   * invalidation-managment infrastructure. Subclasses must implement drawing
   * and picking code.
   * @constructor
   * @extends {HTMLDivElement}
   */
  var DrawableTrack = ui.define('drawable-track', tracing.tracks.Track);

  DrawableTrack.prototype = {
    __proto__: tracing.tracks.Track.prototype,

    decorate: function(viewport) {
      tracing.tracks.Track.prototype.decorate.call(this, viewport);
      this.classList.add('drawable-track');
      this.slices_ = null;

      this.headingDiv_ = document.createElement('heading');
      this.appendChild(this.headingDiv_);

      this.canvasContainer_ = document.createElement('div');
      this.canvasContainer_.className = 'drawable-container';
      this.appendChild(this.canvasContainer_);

      this.viewportChange_ = this.viewportChange_.bind(this);
      this.viewport.addEventListener('change', this.viewportChange_);
    },

    detach: function() {
      this.viewport.removeEventListener('change', this.viewportChange_);
    },

    get heading() {
      return this.headingDiv_.textContent;
    },

    set heading(text) {
      this.headingDiv_.textContent = text;
    },

    set tooltip(text) {
      this.headingDiv_.title = text;
    },

    viewportChange_: function() {
      this.invalidate();
    },

    invalidate: function() {
      if (this.rafPending_)
        return;

      base.requestPreAnimationFrame(function() {
        this.rafPending_ = false;
        base.requestAnimationFrameInThisFrameIfPossible(function() {
          var ctx = this.context();
          if (ctx === undefined)
            return;

          ctx.save();

          var pixelRatio = window.devicePixelRatio || 1;
          var bounds = this.canvasContainer_.getBoundingClientRect();
          var canvasBounds = ctx.canvas.getBoundingClientRect();

          ctx.translate(0, pixelRatio * (bounds.top - canvasBounds.top));

          var viewLWorld = this.viewport.xViewToWorld(0);
          var viewRWorld = this.viewport.xViewToWorld(
              bounds.width * pixelRatio);
          this.draw(viewLWorld, viewRWorld);

          this.viewport.drawGridLines(ctx, viewLWorld, viewRWorld);
          this.viewport.drawMarkerLines(ctx, viewLWorld, viewRWorld);

          ctx.restore();
        }, this);
      }, this);
      this.rafPending_ = true;
    },

    draw: function(viewLWorld, viewRWorld) {
      throw new Error('Implementation missing');
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
    }
  };

  return {
    DrawableTrack: DrawableTrack
  };
});
