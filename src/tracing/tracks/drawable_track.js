// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracing.tracks.drawable_track');
base.requireStylesheet('tracing.tracks.drawing_container');

base.require('base.raf');
base.require('tracing.constants');
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
      this.headingDiv_.style.width = tracing.constants.HEADING_WIDTH + 'px';
      this.appendChild(this.headingDiv_);
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

    draw: function(type, viewLWorld, viewRWorld) {
      throw new Error('draw implementation missing');
    }
  };

  return {
    DrawableTrack: DrawableTrack
  };
});
