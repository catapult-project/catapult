// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.tracks.track');
base.require('tracing.filter');
base.require('ui');

base.exportTo('tracing.tracks', function() {

  /**
   * A generic track that contains other tracks as its children.
   * @constructor
   */
  var ContainerTrack = ui.define('container-track', tracing.tracks.Track);
  ContainerTrack.prototype = {
    __proto__: tracing.tracks.Track.prototype,

    decorate: function(viewport) {
      tracing.tracks.Track.prototype.decorate.call(this, viewport);
    },

    detach: function() {
      this.textContent = '';
    },

    get tracks_() {
      var tracks = [];
      for (var i = 0; i < this.children.length; i++) {
        if (this.children[i].classList.contains('track'))
          tracks.push(this.children[i]);
      }
      return tracks;
    },

    drawTrack: function(type) {
      for (var i = 0; i < this.children.length; ++i) {
        if (!(this.children[i] instanceof tracing.tracks.Track))
          continue;
        this.children[i].drawTrack(type);
      }
    },

    /**
     * Adds items intersecting the given range to a selection.
     * @param {number} loVX Lower X bound of the interval to search, in
     *     viewspace.
     * @param {number} hiVX Upper X bound of the interval to search, in
     *     viewspace.
     * @param {number} loY Lower Y bound of the interval to search, in
     *     viewspace space.
     * @param {number} hiY Upper Y bound of the interval to search, in
     *     viewspace space.
     * @param {Selection} selection Selection to which to add hits.
     */
    addIntersectingItemsInRangeToSelection: function(
        loVX, hiVX, loY, hiY, selection) {
      for (var i = 0; i < this.tracks_.length; i++) {
        var trackClientRect = this.tracks_[i].getBoundingClientRect();
        var a = Math.max(loY, trackClientRect.top);
        var b = Math.min(hiY, trackClientRect.bottom);
        if (a <= b)
          this.tracks_[i].addIntersectingItemsInRangeToSelection(
              loVX, hiVX, loY, hiY, selection);
      }

      tracing.tracks.Track.prototype.addIntersectingItemsInRangeToSelection.
          apply(this, arguments);
    },

    addAllObjectsMatchingFilterToSelection: function(filter, selection) {
      for (var i = 0; i < this.tracks_.length; i++)
        this.tracks_[i].addAllObjectsMatchingFilterToSelection(
            filter, selection);
    }
  };

  return {
    ContainerTrack: ContainerTrack
  };
});
