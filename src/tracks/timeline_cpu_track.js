// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracks.timeline_container_track');
base.require('tracks.timeline_slice_track');
base.require('timeline_filter');
base.require('timeline_model');
base.require('ui');
base.exportTo('tracks', function() {

  /**
   * Visualizes a TimelineCpu using a series of of TimelineSliceTracks.
   * @constructor
   */
  var TimelineCpuTrack = base.ui.define(tracks.TimelineContainerTrack);
  TimelineCpuTrack.prototype = {
    __proto__: tracks.TimelineContainerTrack.prototype,

    decorate: function() {
      this.classList.add('timeline-cpu-track');
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

    applyCategoryFilter_: function() {
      if (this.categoryFilter.matchCpu(this.cpu_))
        this.updateChildTracks_();
      else
        this.visible = false;
    },

    updateChildTracks_: function() {
      this.detach();
      if (this.cpu_) {
        var slices = tracing.filterSliceArray(this.categoryFilter_,
                                              this.cpu_.slices);
        if (slices.length) {
          var track = new tracks.TimelineSliceTrack();
          track.slices = slices;
          track.heading = this.heading_;
          track.tooltip = this.tooltip_;
          this.addTrack_(track);
        }

        for (var counterName in this.cpu_.counters) {
          var counter = this.cpu_.counters[counterName];
          track = new tracks.TimelineCounterTrack();
          track.heading = 'CPU ' + this.cpu_.cpuNumber + ' ' +
              counter.name + ':';
          track.counter = counter;
          this.addTrack_(track);
        }
      }
      this.addControlButtonElements_(false);
    }
  };

  return {
    TimelineCpuTrack: TimelineCpuTrack
  };
});
