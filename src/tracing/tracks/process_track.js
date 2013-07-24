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
          this.drawEvents_(
              this.processBase.instantEvents,
              worldBounds.left,
              worldBounds.right);
          ctx.restore();
          break;

        case tracing.tracks.DrawType.BACKGROUND:
          this.drawBackground_();
          // Don't bother recursing further, Process is the only level that
          // draws backgrounds.
          return;
      }

      tracing.tracks.ContainerTrack.prototype.drawTrack.call(this, type);
    },

    drawBackground_: function() {
      var ctx = this.context();
      if (ctx === undefined)
        return;

      ctx.save();
      ctx.fillStyle = '#eee';

      var canvasBounds = ctx.canvas.getBoundingClientRect();
      var draw = false;
      for (var i = 0; i < this.children.length; ++i) {
        if (!(this.children[i] instanceof tracing.tracks.Track) ||
            (this.children[i] instanceof tracing.tracks.SpacingTrack))
          continue;

        draw = !draw;
        if (!draw)
          continue;

        var pixelRatio = window.devicePixelRatio || 1;

        var bounds = this.children[i].getBoundingClientRect();
        ctx.fillRect(0,
                     (bounds.top - canvasBounds.top) * pixelRatio,
                     ctx.canvas.width * pixelRatio,
                     bounds.height * pixelRatio);
      }
      ctx.restore();
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
