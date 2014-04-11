// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.tracks.container_track');
tvcm.require('tracing.tracks.slice_track');
tvcm.require('tracing.filter');
tvcm.require('tracing.trace_model');
tvcm.require('tvcm.ui');

tvcm.exportTo('tracing.tracks', function() {

  /**
   * Visualizes a Cpu using a series of of SliceTracks.
   * @constructor
   */
  var CpuTrack =
      tvcm.ui.define('cpu-track', tracing.tracks.ContainerTrack);
  CpuTrack.prototype = {
    __proto__: tracing.tracks.ContainerTrack.prototype,

    decorate: function(viewport) {
      tracing.tracks.ContainerTrack.prototype.decorate.call(this, viewport);
      this.classList.add('cpu-track');
    },

    get cpu() {
      return this.cpu_;
    },

    set cpu(cpu) {
      this.cpu_ = cpu;
      this.updateContents_();
    },

    get tooltip() {
      return this.tooltip_;
    },

    set tooltip(value) {
      this.tooltip_ = value;
      this.updateContents_();
    },

    get hasVisibleContent() {
      return this.children.length > 0;
    },

    updateContents_: function() {
      this.detach();
      if (!this.cpu_)
        return;
      var slices = this.cpu_.slices;
      if (slices.length) {
        var track = new tracing.tracks.SliceTrack(this.viewport);
        track.slices = slices;
        track.heading = this.cpu_.userFriendlyName + ':';
        this.appendChild(track);
      }

      this.appendSamplesTracks_();

      for (var counterName in this.cpu_.counters) {
        var counter = this.cpu_.counters[counterName];
        track = new tracing.tracks.CounterTrack(this.viewport);
        track.heading = this.cpu_.userFriendlyName + ' ' +
            counter.name + ':';
        track.counter = counter;
        this.appendChild(track);
      }
    },

    appendSamplesTracks_: function() {
      var samples = this.cpu_.samples;
      if (samples === undefined || samples.length === 0)
        return;
      var samplesByTitle = {};
      samples.forEach(function(sample) {
        if (samplesByTitle[sample.title] === undefined)
          samplesByTitle[sample.title] = [];
        samplesByTitle[sample.title].push(sample);
      });

      var sampleTitles = tvcm.dictionaryKeys(samplesByTitle);
      sampleTitles.sort();

      sampleTitles.forEach(function(sampleTitle) {
        var samples = samplesByTitle[sampleTitle];
        var samplesTrack = new tracing.tracks.SliceTrack(this.viewport);
        samplesTrack.group = this.cpu_;
        samplesTrack.slices = samples;
        samplesTrack.heading = this.cpu_.userFriendlyName + ': ' +
            sampleTitle;
        samplesTrack.tooltip = this.cpu_.userFriendlyDetails;
        samplesTrack.selectionGenerator = function() {
          var selection = new tracing.Selection();
          for (var i = 0; i < samplesTrack.slices.length; i++) {
            selection.push(samplesTrack.slices[i]);
          }
          return selection;
        };
        this.appendChild(samplesTrack);
      }, this);
    }
  };

  return {
    CpuTrack: CpuTrack
  };
});
