// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracing.tracks.drawing_container');

base.require('tracing.tracks.track');
base.require('ui');

base.exportTo('tracing.tracks', function() {
  var DrawingContainer = ui.define('drawing-container', tracing.tracks.Track);

  DrawingContainer.prototype = {
    __proto__: tracing.tracks.Track.prototype,

    decorate: function(viewport) {
      tracing.tracks.Track.prototype.decorate.call(this, viewport);
      this.classList.add('drawing-container');

      this.canvas_ = document.createElement('canvas');
      this.canvas_.className = 'drawing-container-canvas';
      this.appendChild(this.canvas_);

      this.ctx_ = this.canvas_.getContext('2d');

      this.viewportChange_ = this.viewportChange_.bind(this);
      this.viewport.addEventListener('change', this.viewportChange_);
    },

    // Needed to support the calls in TimelineTrackView.
    get canvas() {
      return this.canvas_;
    },

    context: function() {
      return this.ctx_;
    },

    viewportChange_: function() {
      this.invalidate();
    },

    invalidate: function() {
      if (this.rafPending_)
        return;
      this.rafPending_ = true;

      base.requestPreAnimationFrame(function() {
        this.rafPending_ = false;
        this.ctx_.clearRect(0, 0, this.canvas_.width, this.canvas_.height);
        this.updateCanvasSizeIfNeeded_();
      }, this);
    },

    updateCanvasSizeIfNeeded_: function() {
      // Find the first heading with size.
      var headings = this.querySelectorAll('heading');
      if (headings === undefined || headings === null || headings.length === 0)
        return;
      var headingBounds = undefined;
      for (var i = 0; i < headings.length; i++) {
        var rect = headings[i].getBoundingClientRect();
        if (rect.right > 0) {
          headingBounds = rect;
          break;
        }
      }
      if (headingBounds === undefined)
        return;

      var visibleChildTracks = base.asArray(this.children).filter(
          this.visibleFilter_);

      var thisBounds = this.getBoundingClientRect();
      var firstChildTrackBounds = visibleChildTracks[0].getBoundingClientRect();
      var lastChildTrackBounds =
          visibleChildTracks[visibleChildTracks.length - 1].
              getBoundingClientRect();

      var canvasLeft = headingBounds.right - thisBounds.left;
      var canvasTop = firstChildTrackBounds.top - thisBounds.top +
                      this.scrollTop;

      if (this.canvas_.style.top + 'px' !== canvasTop)
        this.canvas_.style.top = canvasTop + 'px';
      if (this.canvas_.style.left + 'px' !== canvasLeft)
        this.canvas_.style.left = canvasLeft + 'px';

      var innerWidth = firstChildTrackBounds.width - headingBounds.right;
      var innerHeight = lastChildTrackBounds.bottom - firstChildTrackBounds.top;

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

    visibleFilter_: function(element) {
      if (!(element instanceof tracing.tracks.Track))
        return false;
      return window.getComputedStyle(element).display !== 'none';
    }
  };

  return {
    DrawingContainer: DrawingContainer
  };
});
