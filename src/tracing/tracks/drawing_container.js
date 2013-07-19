// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracing.tracks.drawing_container');

base.require('base.raf');
base.require('tracing.tracks.track');
base.require('ui');

base.exportTo('tracing.tracks', function() {
  var DrawType = {
    SLICE: 1,
    INSTANT_EVENT: 2
  };

  var DrawingContainer = ui.define('drawing-container', tracing.tracks.Track);

  DrawingContainer.prototype = {
    __proto__: tracing.tracks.Track.prototype,

    decorate: function(viewport) {
      tracing.tracks.Track.prototype.decorate.call(this, viewport);
      this.classList.add('drawing-container');

      this.canvas_ = document.createElement('canvas');
      this.canvas_.className = 'drawing-container-canvas';
      this.canvas_.style.left = tracing.constants.HEADING_WIDTH + 'px';
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

        base.requestAnimationFrameInThisFrameIfPossible(function() {
          for (var i = 0; i < this.children.length; ++i) {
            if (!(this.children[i] instanceof tracing.tracks.Track))
              continue;
            this.children[i].drawTrack(DrawType.INSTANT_EVENT);
          }

          for (var i = 0; i < this.children.length; ++i) {
            if (!(this.children[i] instanceof tracing.tracks.Track))
              continue;
            this.children[i].drawTrack(DrawType.SLICE);
          }

          var pixelRatio = window.devicePixelRatio || 1;
          var bounds = this.canvas_.getBoundingClientRect();
          var viewLWorld = this.viewport.xViewToWorld(0);
          var viewRWorld = this.viewport.xViewToWorld(
              bounds.width * pixelRatio);

          this.viewport.drawGridLines(this.ctx_, viewLWorld, viewRWorld);
          this.viewport.drawMarkerLines(this.ctx_, viewLWorld, viewRWorld);
        }, this);
      }, this);
    },

    updateCanvasSizeIfNeeded_: function() {
      var visibleChildTracks =
          base.asArray(this.children).filter(this.visibleFilter_);

      var thisBounds = this.getBoundingClientRect();

      var firstChildTrackBounds = visibleChildTracks[0].getBoundingClientRect();
      var lastChildTrackBounds =
          visibleChildTracks[visibleChildTracks.length - 1].
              getBoundingClientRect();

      var innerWidth = firstChildTrackBounds.width -
          tracing.constants.HEADING_WIDTH;
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

      var canvasTop =
          firstChildTrackBounds.top - thisBounds.top + this.scrollTop;
      if (this.canvas_.style.top + 'px' !== canvasTop)
        this.canvas_.style.top = canvasTop + 'px';
    },

    visibleFilter_: function(element) {
      if (!(element instanceof tracing.tracks.Track))
        return false;
      return window.getComputedStyle(element).display !== 'none';
    }
  };

  return {
    DrawingContainer: DrawingContainer,
    DrawType: DrawType
  };
});
