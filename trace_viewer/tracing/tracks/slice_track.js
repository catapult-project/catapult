// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.tracks.rect_track');

tvcm.exportTo('tracing.tracks', function() {

  /**
   * A track that displays an array of Slice objects.
   * @constructor
   * @extends {HeadingTrack}
   */
  var SliceTrack = tvcm.ui.define(
      'slice-track', tracing.tracks.RectTrack);

  SliceTrack.prototype = {

    __proto__: tracing.tracks.RectTrack.prototype,

    decorate: function(viewport) {
      tracing.tracks.RectTrack.prototype.decorate.call(this, viewport);
    },

    get slices() {
      return this.rects;
    },

    set slices(slices) {
      this.rects = slices;
    }
  };

  return {
    SliceTrack: SliceTrack
  };
});
