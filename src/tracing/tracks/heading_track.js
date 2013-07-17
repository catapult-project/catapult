// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracing.tracks.heading_track');

base.require('tracing.constants');
base.require('tracing.tracks.track');
base.require('ui');

base.exportTo('tracing.tracks', function() {
  /**
   * A track with a header. Provides the basic heading and tooltip
   * infrastructure. Subclasses must implement drawing code.
   * @constructor
   * @extends {HTMLDivElement}
   */
  var HeadingTrack = ui.define('heading-track', tracing.tracks.Track);

  HeadingTrack.prototype = {
    __proto__: tracing.tracks.Track.prototype,

    decorate: function(viewport) {
      tracing.tracks.Track.prototype.decorate.call(this, viewport);
      this.classList.add('heading-track');

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
    HeadingTrack: HeadingTrack
  };
});
