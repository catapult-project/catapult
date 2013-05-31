// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracing.tracks.trace_model_track');

base.require('base.measuring_stick');
base.require('tracing.tracks.container_track');
base.require('tracing.tracks.cpu_track');
base.require('tracing.tracks.process_track');

base.require('ui');

base.exportTo('tracing.tracks', function() {

  /**
   * Visualizes a Model by building ProcessTracks and
   * CpuTracks.
   * @constructor
   */
  var TraceModelTrack = ui.define(
      'trace-model-track', tracing.tracks.ContainerTrack);

  TraceModelTrack.prototype = {

    __proto__: tracing.tracks.ContainerTrack.prototype,

    decorate: function() {
      this.classList.add('model-track');
      this.measuringStick_ = new base.MeasuringStick();
      this.measuringStick_.attach();
    },

    detach: function() {
      tracing.tracks.ContainerTrack.prototype.detach.call(this);
      this.measuringStick_.detach();
    },

    get model() {
      return this.model_;
    },

    set model(model) {
      this.model_ = model;
      this.updateHeadingWidth_();
      this.updateChildTracks_();
    },

    updateHeadingWidth_: function() {
      // Figure out all the headings.
      var allHeadings = [];
      this.model.getAllThreads().forEach(function(t) {
        allHeadings.push(t.userFriendlyName);
      });
      this.model.getAllCounters().forEach(function(c) {
        allHeadings.push(c.name);
      });
      this.model.getAllCpus().forEach(function(c) {
        allHeadings.push('CPU ' + c.cpuNumber);
      });

      // Figure out the maximum heading size.
      var maxHeadingWidth = 0;
      var headingEl = document.createElement('div');
      headingEl.style.position = 'fixed';
      headingEl.className = 'canvas-based-track-title';
      for (var i = 0; i < allHeadings.length; i++) {
        var text = allHeadings[i];
        headingEl.textContent = text + ':__';
        var w = this.measuringStick_.measure(headingEl).width;
        // Limit heading width to 300px.
        if (w > 300)
          w = 300;
        if (w > maxHeadingWidth)
          maxHeadingWidth = w;
      }
      this.headingWidth = maxHeadingWidth + 'px';
    },

    updateChildTracks_: function() {
      this.detachAllChildren();
      if (this.model_) {
        var cpus = this.model_.getAllCpus();
        cpus.sort(tracing.trace_model.Cpu.compare);

        for (var i = 0; i < cpus.length; ++i) {
          var cpu = cpus[i];
          var track = new tracing.tracks.CpuTrack();
          track.heading = 'CPU ' + cpu.cpuNumber + ':';
          track.cpu = cpu;
          this.addTrack_(track);
        }

        // Get a sorted list of processes.
        var processes = this.model_.getAllProcesses();
        processes.sort(tracing.trace_model.Process.compare);

        for (var i = 0; i < processes.length; ++i) {
          var process = processes[i];
          var track = new tracing.tracks.ProcessTrack();
          track.process = process;
          this.addTrack_(track);
        }
      }
    }
  };

  return {
    TraceModelTrack: TraceModelTrack
  };
});
