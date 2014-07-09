// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.tracks.rect_track');

tvcm.exportTo('tracing.tracks', function() {

  /**
   * A track that displays an array of Sample objects.
   * @constructor
   * @extends {HeadingTrack}
   */
  var SampleTrack = tvcm.ui.define(
      'sample-track', tracing.tracks.RectTrack);

  SampleTrack.prototype = {

    __proto__: tracing.tracks.RectTrack.prototype,

    decorate: function(viewport) {
      tracing.tracks.RectTrack.prototype.decorate.call(this, viewport);
    },

    get samples() {
      return this.rects;
    },

    set samples(samples) {
      this.rects = samples;
    },

    addRectToSelection: function(sample, selection) {
      selection.push(sample);
    }
  };

  return {
    SampleTrack: SampleTrack
  };
});
