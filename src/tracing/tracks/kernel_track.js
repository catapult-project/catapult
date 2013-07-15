// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.tracks.process_track_base');
base.require('tracing.tracks.cpu_track');
base.require('tracing.tracks.spacing_track');

base.exportTo('tracing.tracks', function() {
  var Cpu = tracing.trace_model.Cpu;
  var CpuTrack = tracing.tracks.cpu_track;
  var ProcessTrackBase = tracing.tracks.ProcessTrackBase;
  var SpacingTrack = tracing.tracks.SpacingTrack;

  /**
   * @constructor
   */
  var KernelTrack = ui.define('kernel-track', ProcessTrackBase);

  KernelTrack.prototype = {
    __proto__: ProcessTrackBase.prototype,

    decorate: function(viewport) {
      tracing.tracks.ProcessTrackBase.prototype.decorate.call(this, viewport);
    },


    // Kernel maps to processBase because we derive from ProcessTrackBase.
    set kernel(kernel) {
      this.processBase = kernel;
    },

    get kernel() {
      return this.processBase;
    },

    willAppendTracks_: function() {
      var categoryFilter = this.categoryFilter;

      var cpus = base.dictionaryValues(this.kernel.cpus);
      cpus.sort(tracing.trace_model.Cpu.compare);

      var didAppendAtLeastOneTrack = false;
      for (var i = 0; i < cpus.length; ++i) {
        var cpu = cpus[i];
        if (!categoryFilter.matchCpu(cpu))
          return;
        var track = new tracing.tracks.CpuTrack(this.viewport);
        track.categoryFilter = categoryFilter;
        track.cpu = cpu;
        if (!track.hasVisibleContent)
          continue;
        this.appendChild(track);
        didAppendAtLeastOneTrack = true;
      }
      if (didAppendAtLeastOneTrack)
        this.appendChild(new SpacingTrack(this.viewport));
    }
  };


  return {
    KernelTrack: KernelTrack
  };
});
