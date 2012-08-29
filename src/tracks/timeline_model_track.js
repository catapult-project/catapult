// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracks.timeline_model_track');
base.require('tracks.timeline_container_track');
base.require('tracks.timeline_cpu_track');
base.require('tracks.timeline_process_track');
base.require('ui');

base.exportTo('tracks', function() {

  /**
   * Visualizes a TimelineModel by building TimelineProcessTracks and
   * TimelineCpuTracks.
   * @constructor
   */
  var TimelineModelTrack = base.ui.define(tracks.TimelineContainerTrack);

  TimelineModelTrack.prototype = {

    __proto__: tracks.TimelineContainerTrack.prototype,

    decorate: function() {
      this.classList.add('timeline-model-track');
      this.measuringStick_ = new tracing.MeasuringStick();
      this.measuringStick_.attach();
    },

    detach: function() {
      tracks.TimelineContainerTrack.prototype.detach.call(this);
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
      headingEl.className = 'timeline-canvas-based-track-title';
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
        cpus.sort(tracing.TimelineCpu.compare);

        for (var i = 0; i < cpus.length; ++i) {
          var cpu = cpus[i];
          var track = new tracks.TimelineCpuTrack();
          track.heading = 'CPU ' + cpu.cpuNumber + ':';
          track.cpu = cpu;
          this.addTrack_(track);
        }

        // Get a sorted list of processes.
        var processes = this.model_.getAllProcesses();
        processes.sort(tracing.TimelineProcess.compare);

        for (var i = 0; i < processes.length; ++i) {
          var process = processes[i];
          var track = new tracks.TimelineProcessTrack();
          track.process = process;
          this.addTrack_(track);
        }
      }
    }
  };

  return {
    TimelineModelTrack: TimelineModelTrack
  };
});
