// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.requireStylesheet('tracing.tracks.thread_track');

tvcm.require('tracing.tracks.container_track');
tvcm.require('tracing.tracks.slice_track');
tvcm.require('tracing.tracks.slice_group_track');
tvcm.require('tracing.tracks.async_slice_group_track');
tvcm.require('tracing.filter');
tvcm.require('tvcm.ui');
tvcm.require('tvcm.iteration_helpers');

tvcm.exportTo('tracing.tracks', function() {

  /**
   * Visualizes a Thread using a series of of SliceTracks.
   * @constructor
   */
  var ThreadTrack = tvcm.ui.define('thread-track',
                                   tracing.tracks.ContainerTrack);
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
        asyncTrack.group = this.thread_.asyncSliceGroup;
        if (asyncTrack.hasVisibleContent)
          this.appendChild(asyncTrack);
      }

      this.appendThreadSamplesTracks_();

      if (this.thread_.timeSlices) {
        var timeSlicesTrack = new tracing.tracks.SliceTrack(this.viewport);
        timeSlicesTrack.heading = '';
        timeSlicesTrack.height = '4px';
        timeSlicesTrack.slices = this.thread_.timeSlices;
        if (timeSlicesTrack.hasVisibleContent)
          this.appendChild(timeSlicesTrack);
      }

      if (this.thread_.sliceGroup.length) {
        var track = new tracing.tracks.SliceGroupTrack(this.viewport);
        track.heading = this.thread_.userFriendlyName;
        track.tooltip = this.thread_.userFriendlyDetails;
        track.group = this.thread_.sliceGroup;
        if (track.hasVisibleContent)
          this.appendChild(track);
      }
    },

    appendThreadSamplesTracks_: function() {
      var threadSamples = this.thread_.samples;
      if (threadSamples === undefined || threadSamples.length === 0)
        return;
      var samplesByTitle = {};
      threadSamples.forEach(function(sample) {
        if (samplesByTitle[sample.title] === undefined)
          samplesByTitle[sample.title] = [];
        samplesByTitle[sample.title].push(sample);
      });

      var sampleTitles = tvcm.dictionaryKeys(samplesByTitle);
      sampleTitles.sort();

      sampleTitles.forEach(function(sampleTitle) {
        var samples = samplesByTitle[sampleTitle];
        var samplesTrack = new tracing.tracks.SliceTrack(this.viewport);
        samplesTrack.group = this.thread_;
        samplesTrack.slices = samples;
        samplesTrack.heading = this.thread_.userFriendlyName + ': ' +
            sampleTitle;
        samplesTrack.tooltip = this.thread_.userFriendlyDetails;
        samplesTrack.selectionGenerator = function() {
          var selection = new tracing.Selection();
          for (var i = 0; i < samplesTrack.slices.length; i++) {
            selection.push(samplesTrack.slices[i]);
          }
          return selection;
        };
        this.appendChild(samplesTrack);
      }, this);
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
