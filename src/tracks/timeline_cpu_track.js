// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.defineModule('tracks.timeline_cpu_track')
    .dependsOn('tracks.timeline_container_track',
               'tracks.timeline_slice_track',
               'timeline_filter',
               'timeline_model',
               'ui')
    .exportsTo('tracks', function() {

  /**
   * Visualizes a TimelineCpu using a series of of TimelineSliceTracks.
   * @constructor
   */
  var TimelineCpuTrack = base.ui.define(tracks.TimelineContainerTrack);
  TimelineCpuTrack.prototype = {
    __proto__: tracks.TimelineContainerTrack.prototype,

    decorate: function() {
      this.classList.add('timeline-thread-track');
    },

    set categoryFilter(v) {
      this.categoryFilter_ = v;
      this.updateChildTracks_();
    },

    get cpu() {
      return this.cpu_;
    },

    set cpu(cpu) {
      this.cpu_ = cpu;
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

    updateChildTracks_: function() {
      this.detach();
      this.textContent = '';
      this.tracks_ = [];
      if (this.cpu_) {
        var track = new tracks.TimelineSliceTrack();
        track.slices = tracing.filterSliceArray(this.categoryFilter_,
                                                this.cpu_.slices);
        if (!track.slices.length)
          return;

        track.headingWidth = this.headingWidth_;
        track.viewport = this.viewport_;

        this.tracks_.push(track);
        this.appendChild(track);

        this.tracks_[0].heading = this.heading_;
        this.tracks_[0].tooltip = this.tooltip_;
      }
      this.addControlButtonElements_(false);
    }
  };

  return {
    TimelineCpuTrack: TimelineCpuTrack,
  }
});
