// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracing.tracks.spacing_track');

base.require('tracing.tracks.heading_track');

base.exportTo('tracing.tracks', function() {
  /**
   * @constructor
   */
  var SpacingTrack = ui.define('spacing-track', tracing.tracks.HeadingTrack);

  SpacingTrack.prototype = {
    __proto__: tracing.tracks.HeadingTrack.prototype,

    decorate: function(viewport) {
      tracing.tracks.HeadingTrack.prototype.decorate.call(this, viewport);
      this.classList.add('spacing-track');
    },

    draw: function(type, viewLWorld, viewRWorld) {
    },

    addAllObjectsMatchingFilterToSelection: function(filter, selection) {
    }
  };

  return {
    SpacingTrack: SpacingTrack
  };
});
