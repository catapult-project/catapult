// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.defineModule('tracks.timeline_container_track')
    .dependsOn('tracks.timeline_track',
               'ui')
    .exportsTo('tracks', function() {

  /**
   * A generic track that contains other tracks as its children.
   * @constructor
   */
  var TimelineContainerTrack = base.ui.define(tracks.TimelineTrack);
  TimelineContainerTrack.prototype = {
    __proto__: tracks.TimelineTrack.prototype,

    decorate: function() {
      this.tracks_ = [];
    },

    detach: function() {
      for (var i = 0; i < this.tracks_.length; i++)
        this.tracks_[i].detach();
      this.tracks_ = [];
    },

    get viewport() {
      return this.viewport_;
    },

    set viewport(v) {
      this.viewport_ = v;
      for (var i = 0; i < this.tracks_.length; i++)
        this.tracks_[i].viewport = v;
      this.updateChildTracks_();
    },

    get firstCanvas() {
      if (this.tracks_.length)
        return this.tracks_[0].firstCanvas;
      return undefined;
    },

    get numVisibleTracks() {
      if (!this.visible)
        return 0;

      var sum = 0;
      for (var i = 0; i < this.tracks_.length; ++i) {
        sum += this.tracks_[i].numVisibleTracks;
      }
      return sum;
    },

    /**
     * Adds items intersecting a point to a selection.
     * @param {number} wX X location to search at, in worldspace.
     * @param {number} wY Y location to search at, in offset space.
     *     offset space.
     * @param {TimelineSelection} selection Selection to which to add hits.
     * @return {boolean} true if a slice was found, otherwise false.
     */
    addIntersectingItemsToSelection: function(wX, wY, selection) {
      for (var i = 0; i < this.tracks_.length; i++) {
        var trackClientRect = this.tracks_[i].getBoundingClientRect();
        if (wY >= trackClientRect.top && wY < trackClientRect.bottom)
          this.tracks_[i].addIntersectingItemsToSelection(wX, wY, selection);
      }
      return false;
    },

    /**
     * Adds items intersecting the given range to a selection.
     * @param {number} loWX Lower X bound of the interval to search, in
     *     worldspace.
     * @param {number} hiWX Upper X bound of the interval to search, in
     *     worldspace.
     * @param {number} loY Lower Y bound of the interval to search, in
     *     offset space.
     * @param {number} hiY Upper Y bound of the interval to search, in
     *     offset space.
     * @param {TimelineSelection} selection Selection to which to add hits.
     */
    addIntersectingItemsInRangeToSelection: function(
        loWX, hiWX, loY, hiY, selection) {
      for (var i = 0; i < this.tracks_.length; i++) {
        var trackClientRect = this.tracks_[i].getBoundingClientRect();
        var a = Math.max(loY, trackClientRect.top);
        var b = Math.min(hiY, trackClientRect.bottom);
        if (a <= b)
          this.tracks_[i].addIntersectingItemsInRangeToSelection(
              loWX, hiWX, loY, hiY, selection);
      }
    },

    addAllObjectsMatchingFilterToSelection: function(filter, selection) {
      for (var i = 0; i < this.tracks_.length; i++)
        this.tracks_[i].addAllObjectsMatchingFilterToSelection(
          filter, selection);
    }
  };

  return {
    TimelineContainerTrack: TimelineContainerTrack,
  }
});
