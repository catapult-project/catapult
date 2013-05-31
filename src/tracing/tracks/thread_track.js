// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracing.tracks.thread_track');

base.require('tracing.tracks.container_track');
base.require('tracing.tracks.slice_track');
base.require('tracing.tracks.slice_group_track');
base.require('tracing.tracks.async_slice_group_track');
base.require('tracing.filter');
base.require('ui');

base.exportTo('tracing.tracks', function() {

  /**
   * Visualizes a Thread using a series of of SliceTracks.
   * @constructor
   */
  var ThreadTrack = ui.define('thread-track', tracing.tracks.ContainerTrack);
  ThreadTrack.prototype = {
    __proto__: tracing.tracks.ContainerTrack.prototype,

    decorate: function() {
      this.classList.add('thread-track');
      this.categoryFilter_ = new tracing.Filter();
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

    applyCategoryFilter_: function() {
      this.updateVisibility_();
    },

    updateChildTracks_: function() {
      this.detach();
      if (this.thread_) {
        var cpuTrack = new tracing.tracks.SliceTrack();
        cpuTrack.heading = '';
        cpuTrack.slices = this.thread_.cpuSlices;
        cpuTrack.height = '4px';
        cpuTrack.decorateHit = function(hit) {
          hit.thread = this.thread_;
        }
        this.addTrack_(cpuTrack);

        var asyncTrack = new tracing.tracks.AsyncSliceGroupTrack();
        asyncTrack.categoryFilter = this.categoryFilter;
        asyncTrack.decorateHit = function(hit) {
          // TODO(simonjam): figure out how to associate subSlice hits back
          // to their parent slice.
        }
        asyncTrack.group = this.thread_.asyncSlices;
        this.addTrack_(asyncTrack);

        var track = new tracing.tracks.SliceGroupTrack();
        track.decorateHit = function(hit) {
          hit.thread = this.thread_;
        }
        track.group = this.thread_;
        this.addTrack_(track);

        if (this.thread_.samples.length) {
          var samplesTrack = new tracing.tracks.SliceTrack();
          samplesTrack.group = this.thread_;
          samplesTrack.slices = this.thread_.samples;
          samplesTrack.decorateHit = function(hit) {
            // TODO(johnmccutchan): Figure out what else should be associated
            // with the hit.
            hit.thread = this.thread_;
          }
          this.addTrack_(samplesTrack);
        }

        this.updateVisibility_();
      }
      this.addControlButtonElements_();
    },

    updateVisibility_: function() {
      if (!this.categoryFilter.matchThread(this.thread)) {
        this.visible = false;
        return;
      }
      var shouldBeVisible = false;
      for (var i = 0; i < this.tracks_.length; ++i) {
        var track = this.tracks_[i];
        if (track.visible) {
          shouldBeVisible = true;
          if (i >= 1) {
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
    ThreadTrack: ThreadTrack
  };
});
