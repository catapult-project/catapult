// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.defineModule('tracks.timeline_container_track')
    .dependsOn('tracks.timeline_track',
               'timeline_filter',
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
      this.categoryFilter_ = new tracing.TimelineFilter();
      this.headingWidth_ = undefined;
      this.tracks_ = [];
    },

    detach: function() {
      for (var i = 0; i < this.tracks_.length; i++)
        this.tracks_[i].detach();
      this.tracks_ = [];
      this.textContent = '';
    },

    get viewport() {
      return this.viewport_;
    },

    set viewport(v) {
      this.viewport_ = v;
      for (var i = 0; i < this.tracks_.length; i++)
        this.tracks_[i].viewport = v;
    },

    get firstCanvas() {
      if (this.tracks_.length)
        return this.tracks_[0].firstCanvas;
      return undefined;
    },

    // The number of tracks actually displayed.
    get numVisibleTracks() {
      if (!this.visible)
        return 0;
      return this.numVisibleChildTracks;
    },

    // The number of tracks that would be displayed if this track were visible.
    get numVisibleChildTracks() {
      var sum = 0;
      for (var i = 0; i < this.tracks_.length; ++i) {
        sum += this.tracks_[i].numVisibleTracks;
      }
      return sum;
    },

    get headingWidth() {
      return this.headingWidth_;
    },

    set headingWidth(w) {
      this.headingWidth_ = w;
      for (var i = 0; i < this.tracks_.length; ++i) {
        this.tracks_[i].headingWidth = w;
      }
    },

    get categoryFilter() {
      return this.categoryFilter_;
    },

    set categoryFilter(v) {
      this.categoryFilter_ = v;
      for (var i = 0; i < this.tracks_.length; ++i) {
        this.tracks_[i].categoryFilter = v;
      }
      this.applyCategoryFilter_();
      this.updateFirstVisibleChildCSS();
    },

    applyCategoryFilter_: function() {
    },

    addTrack_: function(track) {
      track.headingWidth = this.headingWidth_;
      track.viewport = this.viewport_;
      track.categoryFilter = this.categoryFilter;

      this.tracks_.push(track);
      this.appendChild(track);
      return track;
    },

    updateFirstVisibleChildCSS: function() {
      var isFirst = true;
      for (var i = 0; i < this.tracks_.length; ++i) {
        var track = this.tracks_[i];
        if (isFirst && track.visible) {
          track.classList.add('first-visible-child');
          isFirst = false;
        } else {
          track.classList.remove('first-visible-child');
        }
      }
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
