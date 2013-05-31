// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracing.tracks.canvas_based_track');

base.require('base.raf');
base.require('tracing.tracks.track');
base.require('tracing.fast_rect_renderer');
base.require('tracing.color_scheme');
base.require('ui');

base.exportTo('tracing.tracks', function() {

  /**
   * A canvas-based track constructed. Provides the basic heading and
   * invalidation-managment infrastructure. Subclasses must implement drawing
   * and picking code.
   * @constructor
   * @extends {HTMLDivElement}
   */
  var CanvasBasedTrack =
      ui.define('canvas-based-track', tracing.tracks.Track);

  CanvasBasedTrack.prototype = {
    __proto__: tracing.tracks.Track.prototype,

    decorate: function() {
      this.className = 'canvas-based-track';
      this.slices_ = null;

      this.headingDiv_ = document.createElement('div');
      this.headingDiv_.className = 'canvas-based-track-title';
      this.appendChild(this.headingDiv_);

      this.canvasContainer_ = document.createElement('div');
      this.canvasContainer_.className =
          'canvas-based-track-canvas-container';
      this.appendChild(this.canvasContainer_);
      this.canvas_ = document.createElement('canvas');
      this.canvas_.className = 'canvas-based-track-canvas';
      this.canvasContainer_.appendChild(this.canvas_);

      this.ctx_ = this.canvas_.getContext('2d');
    },

    detach: function() {
      if (this.viewport_) {
        this.viewport_.removeEventListener('change',
                                           this.viewportChangeBoundToThis_);
        this.viewport_.removeEventListener('markersChange',
            this.viewportMarkersChangeBoundToThis_);
      }
    },

    set headingWidth(width) {
      this.headingDiv_.style.width = width;
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

    get viewport() {
      return this.viewport_;
    },

    set viewport(v) {
      this.viewport_ = v;
      if (this.viewport_) {
        this.viewport_.removeEventListener('change',
                                           this.viewportChangeBoundToThis_);
        this.viewport_.removeEventListener('markersChange',
            this.viewportMarkersChangeBoundToThis_);
      }
      this.viewport_ = v;
      if (this.viewport_) {
        this.viewportChangeBoundToThis_ = this.viewportChange_.bind(this);
        this.viewport_.addEventListener('change',
                                        this.viewportChangeBoundToThis_);
        this.viewportMarkersChangeBoundToThis_ =
            this.viewportMarkersChange_.bind(this);
        this.viewport_.addEventListener('markersChange',
                                        this.viewportMarkersChangeBoundToThis_);
        if (this.isAttachedToDocument_)
          this.updateCanvasSizeIfNeeded_();
      }
      this.invalidate();
    },

    viewportChange_: function() {
      this.invalidate();
    },

    viewportMarkersChange_: function() {
      if (this.viewport_.markers.length < 2)
        this.classList.remove('ruler-track-with-distance-measurements');
      else
        this.classList.add('ruler-track-with-distance-measurements');
    },

    invalidate: function() {
      if (this.rafPending_)
        return;
      base.requestPreAnimationFrame(function() {
        this.rafPending_ = false;
        if (!this.viewport_)
          return;
        this.updateCanvasSizeIfNeeded_();
        base.requestAnimationFrameInThisFrameIfPossible(function() {
          this.redraw();
        }, this);
      }, this);
      this.rafPending_ = true;
    },

    /**
     * @return {boolean} Whether the current timeline is attached to the
     * document.
     */
    get isAttachedToDocument_() {
      var cur = this.parentNode;
      if (!cur)
        return;
      while (cur.parentNode)
        cur = cur.parentNode;
      return cur == this.ownerDocument;
    },

    updateCanvasSizeIfNeeded_: function() {
      var style = window.getComputedStyle(this.canvasContainer_);
      var innerWidth = parseInt(style.width) -
          parseInt(style.paddingLeft) - parseInt(style.paddingRight) -
          parseInt(style.borderLeftWidth) - parseInt(style.borderRightWidth);
      var innerHeight = parseInt(style.height) -
          parseInt(style.paddingTop) - parseInt(style.paddingBottom) -
          parseInt(style.borderTopWidth) - parseInt(style.borderBottomWidth);
      var pixelRatio = window.devicePixelRatio || 1;
      if (this.canvas_.width != innerWidth * pixelRatio) {
        this.canvas_.width = innerWidth * pixelRatio;
        this.canvas_.style.width = innerWidth + 'px';
      }
      if (this.canvas_.height != innerHeight * pixelRatio) {
        this.canvas_.height = innerHeight * pixelRatio;
        this.canvas_.style.height = innerHeight + 'px';
      }
    },

    get firstCanvas() {
      return this.canvas_;
    },

    addIntersectingItemsInRangeToSelection: function(
        loVX, hiVX, loVY, hiVY, selection) {

      var pixelRatio = window.devicePixelRatio || 1;
      var viewPixWidthWorld = this.viewport_.xViewVectorToWorld(1);
      var loWX = this.viewport_.xViewToWorld(loVX * pixelRatio);
      var hiWX = this.viewport_.xViewToWorld(hiVX * pixelRatio);

      var clientRect = this.getBoundingClientRect();
      var a = Math.max(loVY, clientRect.top);
      var b = Math.min(hiVY, clientRect.bottom);
      if (a > b)
        return;

      this.addIntersectingItemsInRangeToSelectionInWorldSpace(
          loWX, hiWX, viewPixWidthWorld, selection);
    }
  };

  return {
    CanvasBasedTrack: CanvasBasedTrack
  };
});
