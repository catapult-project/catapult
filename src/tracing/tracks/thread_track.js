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

    decorate: function(viewport) {
      tracing.tracks.ContainerTrack.prototype.decorate.call(this, viewport);
      this.classList.add('thread-track');
    },

    get thread() {
      return this.thread_;
    },

    set thread(thread) {
      this.thread_ = thread;
      this.updateContents_();
    },

    get hasVisibleContent() {
      return this.tracks_.length > 0;
    },

    updateContents_: function() {
      this.detach();

      if (!this.thread_)
        return;

      this.heading = this.thread_.userFriendlyName + ': ';
      this.tooltip = this.thread_.userFriendlyDetails;

      if (this.thread_.asyncSliceGroup.length) {
        var asyncTrack = new tracing.tracks.AsyncSliceGroupTrack(this.viewport);
        asyncTrack.categoryFilter = this.categoryFilter;
        asyncTrack.decorateHit = function(hit) {
          // TODO(simonjam): figure out how to associate subSlice hits back
          // to their parent slice.
        };
        asyncTrack.group = this.thread_.asyncSliceGroup;
        if (asyncTrack.hasVisibleContent)
          this.appendChild(asyncTrack);
      }

      if (this.thread_.samples.length) {
        var samplesTrack = new tracing.tracks.SliceTrack(this.viewport);
        samplesTrack.categoryFilter = samplesTrack;
        samplesTrack.group = this.thread_;
        samplesTrack.slices = this.thread_.samples;
        samplesTrack.decorateHit = function(hit) {
          // TODO(johnmccutchan): Figure out what else should be associated
          // with the hit.
          hit.thread = this.thread_;
        }
        this.appendChild(samplesTrack);
      }

      if (this.thread_.cpuSlices) {
        var cpuTrack = new tracing.tracks.SliceTrack(this.viewport);
        cpuTrack.categoryFilter = this.categoryFilter;
        cpuTrack.heading = '';
        cpuTrack.height = '4px';
        cpuTrack.decorateHit = function(hit) {
          hit.thread = this.thread_;
        }
        cpuTrack.slices = this.thread_.cpuSlices;
        if (cpuTrack.hasVisibleContent)
          this.appendChild(cpuTrack);
      }

      if (this.thread_.sliceGroup.length) {
        var track = new tracing.tracks.SliceGroupTrack(this.viewport);
        track.categoryFilter = this.categoryFilter;
        track.heading = this.thread_.userFriendlyName;
        track.tooltip = this.thread_.userFriendlyDetails;

        track.decorateHit = function(hit) {
          hit.thread = this.thread_;
        };
        track.group = this.thread_.sliceGroup;
        if (track.hasVisibleContent)
          this.appendChild(track);
      }
    },

    collapsedDidChange: function(collapsed) {
      if (collapsed) {
        var h = parseInt(this.tracks[0].height);
        for (var i = 0; i < this.tracks.length; ++i) {
          if (h > 2) {
            this.tracks[i].height = Math.floor(h) + 'px';
          } else {
            this.tracks[i].style.display = 'none';
          }
          h = h * 0.5;
        }
      } else {
        for (var i = 0; i < this.tracks.length; ++i) {
          this.tracks[i].height = this.tracks[0].height;
          this.tracks[i].style.display = '';
        }
      }
    }
  };

  return {
    ThreadTrack: ThreadTrack
  };
});
