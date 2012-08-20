// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.defineModule('tracks.timeline_thread_track')
    .dependsOn('tracks.timeline_container_track',
               'tracks.timeline_slice_track',
               'tracks.timeline_slice_group_track',
               'tracks.timeline_async_slice_group_track',
               'timeline_filter',
               'ui')
    .exportsTo('tracks', function() {

  /**
   * Visualizes a TimelineThread using a series of of TimelineSliceTracks.
   * @constructor
   */
  var TimelineThreadTrack = base.ui.define(tracks.TimelineContainerTrack);
  TimelineThreadTrack.prototype = {
    __proto__: tracks.TimelineContainerTrack.prototype,

    decorate: function() {
      this.classList.add('timeline-thread-track');
      this.categoryFilter_ = new tracing.TimelineFilter();
    },

    get thread() {
      return this.thread_;
    },

    set thread(thread) {
      this.thread_ = thread;
      this.updateChildTracks_();
    },

    get tooltip() {
      return this.tooltip_;
    },

    set tooltip(value) {
      this.tooltip_ = value;
      this.updateChildTracks_();
    },

    get heading() {
      return this.heading_;
    },

    set heading(h) {
      this.heading_ = h;
      this.updateChildTracks_();
    },

    get headingWidth() {
      return this.headingWidth_;
    },

    set headingWidth(width) {
      this.headingWidth_ = width;
      this.updateChildTracks_();
    },

    get categoryFilter() {
      return this.categoryFilter_;
    },

    set categoryFilter(v) {
      this.categoryFilter_ = v;
      for (var i = 0; i < this.tracks_.length; ++i) {
        this.tracks_[i].categoryFilter = v;
      }
      this.updateVisibility_();
    },

    addTrack_: function(slices) {
      var track = new tracks.TimelineSliceTrack();
      track.heading = '';
      track.slices = slices;
      track.headingWidth = this.headingWidth_;
      track.viewport = this.viewport_;

      this.tracks_.push(track);
      this.appendChild(track);
      return track;
    },

    updateChildTracks_: function() {
      this.detach();
      this.textContent = '';
      if (this.thread_) {
        if (this.categoryFilter &&
            !this.categoryFilter.matchThread(this.thread_)) {
          this.visible = false;
          return;
        }
        var cpuTrack = this.addTrack_(this.thread_.cpuSlices);
        cpuTrack.categoryFilter = this.categoryFilter;
        cpuTrack.height = '4px';
        cpuTrack.decorateHit = function(hit) {
          hit.thread = this.thread_;
        }

        var asyncTrack = new tracks.TimelineAsyncSliceGroupTrack();
        asyncTrack.categoryFilter = this.categoryFilter;
        asyncTrack.headingWidth = this.headingWidth_;
        asyncTrack.viewport = this.viewport_;
        asyncTrack.decorateHit = function(hit) {
          // TODO(simonjam): figure out how to associate subSlice hits back
          // to their parent slice.
        }
        asyncTrack.group = this.thread_.asyncSlices;
        this.appendChild(asyncTrack);
        this.tracks_.push(asyncTrack);

        var track = new tracks.TimelineSliceGroupTrack();
        track.categoryFilter = this.categoryFilter;
        track.headingWidth = this.headingWidth_;
        track.viewport = this.viewport_;
        track.decorateHit = function(hit) {
          hit.thread = this.thread_;
        }
        track.group = this.thread_;
        this.appendChild(track);
        this.tracks_.push(track);

        this.updateVisibility_();
      }
      this.addControlButtonElements_(this.tracks_.length >= 4);
    },

    updateVisibility_: function() {
      var shouldBeVisible = false;
      for (var i = 0; i < this.tracks_.length; ++i) {
        var track = this.tracks_[i];
        if (track.visible) {
          shouldBeVisible = true;
          if (i >= 1) {
            track.classList.add('timeline-thread-first-visible-group');
            track.heading = this.heading_;
            track.tooltip = this.tooltip_;
            break;
          }
        }
      }
      this.visible = shouldBeVisible;
    },

    collapsedDidChange: function(collapsed) {
      if (collapsed) {
        var h = parseInt(this.tracks_[0].height);
        for (var i = 0; i < this.tracks_.length; ++i) {
          if (h > 2) {
            this.tracks_[i].height = Math.floor(h) + 'px';
          } else {
            this.tracks_[i].style.display = 'none';
          }
          h = h * 0.5;
        }
      } else {
        for (var i = 0; i < this.tracks_.length; ++i) {
          this.tracks_[i].height = this.tracks_[0].height;
          this.tracks_[i].style.display = '';
        }
      }
    }
  };

  return {
    TimelineThreadTrack: TimelineThreadTrack,
  }
});
