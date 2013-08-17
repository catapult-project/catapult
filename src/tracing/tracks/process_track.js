// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.tracks.process_track_base');
base.require('tracing.draw_helpers');

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

          var pixelRatio = window.devicePixelRatio || 1;
          var bounds = this.getBoundingClientRect();
          var canvasBounds = ctx.canvas.getBoundingClientRect();

          ctx.save();
          ctx.translate(0, pixelRatio * (bounds.top - canvasBounds.top));

          var dt = this.viewport.currentDisplayTransform;
          var viewLWorld = dt.xViewToWorld(0);
          var viewRWorld = dt.xViewToWorld(
              bounds.width * pixelRatio);

          tracing.drawInstantSlicesAsLines(
              ctx,
              this.viewport.currentDisplayTransform,
              viewLWorld,
              viewRWorld,
              bounds.height,
              this.processBase.instantEvents,
              1);

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
      var canvasBounds = ctx.canvas.getBoundingClientRect();
      var pixelRatio = window.devicePixelRatio || 1;

      var draw = false;
      ctx.fillStyle = '#eee';
      for (var i = 0; i < this.children.length; ++i) {
        if (!(this.children[i] instanceof tracing.tracks.Track) ||
            (this.children[i] instanceof tracing.tracks.SpacingTrack))
          continue;

        draw = !draw;
        if (!draw)
          continue;

        var bounds = this.children[i].getBoundingClientRect();
        ctx.fillRect(0, pixelRatio * (bounds.top - canvasBounds.top),
            ctx.canvas.width, pixelRatio * bounds.height);
      }
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
        selection.push(instantEvent);
      }
      base.iterateOverIntersectingIntervals(this.processBase.instantEvents,
          function(x) { return x.start; },
          function(x) { return x.duration; },
          loWX, hiWX,
          onPickHit.bind(this));

      tracing.tracks.ContainerTrack.prototype.
          addIntersectingItemsInRangeToSelectionInWorldSpace.
          apply(this, arguments);
    },

    addClosestEventToSelection: function(worldX, worldMaxDist, loY, hiY,
                                         selection) {
      this.addClosestInstantEventToSelection(this.processBase.instantEvents,
                                             worldX, worldMaxDist, selection);
      tracing.tracks.ContainerTrack.prototype.addClosestEventToSelection.
          apply(this, arguments);
    }
  };

  return {
    ProcessTrack: ProcessTrack
  };
});
