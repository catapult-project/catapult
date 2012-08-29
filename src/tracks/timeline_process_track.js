// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracks.timeline_container_track');
base.require('tracks.timeline_counter_track');
base.require('tracks.timeline_thread_track');
base.require('timeline_filter');
base.require('ui');

base.exportTo('tracks', function() {

  /**
   * Visualizes a TimelineProcess by building TimelineThreadTracks and
   * TimelineCounterTracks.
   * @constructor
   */
  var TimelineProcessTrack = base.ui.define(tracks.TimelineContainerTrack);

  TimelineProcessTrack.prototype = {

    __proto__: tracks.TimelineContainerTrack.prototype,

    decorate: function() {
      this.classList.add('timeline-process-track');
      this.categoryFilter_ = new tracing.TimelineFilter();
    },

    get process() {
      return this.process_;
    },

    set process(process) {
      this.process_ = process;
      this.updateChildTracks_();
    },

    applyCategoryFilter_: function() {
      this.visible = (this.categoryFilter.matchProcess(this.process) &&
                      !!this.numVisibleChildTracks);
    },

    updateChildTracks_: function() {
      this.detach();
      if (this.process_) {
        // Add counter tracks for this process.
        var counters = [];
        for (var tid in this.process.counters) {
          counters.push(this.process.counters[tid]);
        }
        counters.sort(tracing.TimelineCounter.compare);

        // Create the counters for this process.
        counters.forEach(function(counter) {
          var track = new tracks.TimelineCounterTrack();
          track.heading = counter.name + ':';
          track.counter = counter;
          this.addTrack_(track);
        }.bind(this));

        // Get a sorted list of threads.
        var threads = [];
        for (var tid in this.process.threads)
          threads.push(this.process.threads[tid]);
        threads.sort(tracing.TimelineThread.compare);

        // Create the threads.
        threads.forEach(function(thread) {
          var track = new tracks.TimelineThreadTrack();
          track.heading = thread.userFriendlyName + ':';
          track.tooltip = thread.userFriendlyDetails;
          track.thread = thread;
          this.addTrack_(track);
        }.bind(this));
      }
    }
  };

  return {
    TimelineProcessTrack: TimelineProcessTrack
  };
});
