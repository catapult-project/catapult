// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.tracks.process_track_base');

base.exportTo('tracing.tracks', function() {
  var ProcessTrackBase = tracing.tracks.ProcessTrackBase;

  /**
   * @constructor
   */
  var ProcessTrack = ui.define('process-track', ProcessTrackBase);

  ProcessTrack.prototype = {
    __proto__: ProcessTrackBase.prototype,

    decorate: function(viewport) {
      tracing.tracks.ProcessTrackBase.prototype.decorate.call(this, viewport);
    },

    drawTrack: function(type) {
      switch (type) {
        case tracing.tracks.DrawType.INSTANT_EVENT:
          if (!this.processBase.instantEvents ||
              this.processBase.instantEvents.length === 0)
            break;

          var ctx = this.context();
          if (ctx === undefined)
            break;

          ctx.save();
          var worldBounds = this.setupCanvasForDraw_();
          this.drawInstantEvents_(
              this.processBase.instantEvents,
              worldBounds.left,
              worldBounds.right);
          ctx.restore();
          break;
      }

      tracing.tracks.ContainerTrack.prototype.drawTrack.call(this, type);
    },

    // Process maps to processBase because we derive from ProcessTrackBase.
    set process(process) {
      this.processBase = process;
    },

    get process() {
      return this.processBase;
    },

    addIntersectingItemsInRangeToSelectionInWorldSpace: function(
        loWX, hiWX, viewPixWidthWorld, selection) {
      function onPickHit(instantEvent) {
        var hit = selection.addSlice(this, instantEvent);
        this.decorateHit(hit);
      }
      base.iterateOverIntersectingIntervals(this.processBase.instantEvents,
          function(x) { return x.start; },
          function(x) { return x.duration; },
          loWX, hiWX,
          onPickHit.bind(this));

      tracing.tracks.ContainerTrack.prototype.
          addIntersectingItemsInRangeToSelectionInWorldSpace.
          apply(this, arguments);
    }
  };

  return {
    ProcessTrack: ProcessTrack
  };
});
