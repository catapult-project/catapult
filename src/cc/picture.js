// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.guid');
base.require('base.rect');
base.require('base.raf');
base.require('tracing.trace_model.object_instance');
base.require('cc.picture_as_image_data');
base.require('cc.util');

base.exportTo('cc', function() {

  var ObjectSnapshot = tracing.trace_model.ObjectSnapshot;

  // Number of pictures created. Used as an uniqueId because we are immutable.
  var PictureCount = 0;
  var OPS_TIMING_ITERATIONS = 3;

  /**
   * @constructor
   */
  function PictureSnapshot() {
    ObjectSnapshot.apply(this, arguments);
    this.guid_ = base.GUID.allocate();
  }

  PictureSnapshot.CanRasterize = function() {
    if (!window.chrome)
      return false;
    if (!window.chrome.skiaBenchmarking)
      return false;
    if (!window.chrome.skiaBenchmarking.rasterize)
      return false;
    return true;
  }

  PictureSnapshot.CanGetOps = function() {
    if (!window.chrome)
      return false;
    if (!window.chrome.skiaBenchmarking)
      return false;
    if (!window.chrome.skiaBenchmarking.getOps)
      return false;
    return true;
  }

  PictureSnapshot.CanGetOpTimings = function() {
    if (!window.chrome)
      return false;
    if (!window.chrome.skiaBenchmarking)
      return false;
    if (!window.chrome.skiaBenchmarking.getOpTimings)
      return false;
    return true;
  }

  PictureSnapshot.HowToEnablePictureDebugging = function() {
    var usualReason = [
      'For pictures to show up, you need to have Chrome running with ',
      '--enable-skia-benchmarking. Please restart chrome with this flag ',
      'and try again.'
    ].join('');

    if (!window.chrome)
      return usualReason;
    if (!window.chrome.skiaBenchmarking)
      return usualReason;
    if (!window.chrome.skiaBenchmarking.rasterize)
      return 'Your chrome is old';
    if (!window.chrome.skiaBenchmarking.getOps)
      return 'Your chrome is old: skiaBenchmarking.getOps not found';
    if (!window.chrome.skiaBenchmarking.getOpTimings)
      return 'Your chrome is old: skiaBenchmarking.getOpTimings not found';
    return 'Rasterizing is on';
  }

  PictureSnapshot.prototype = {
    __proto__: ObjectSnapshot.prototype,

    preInitialize: function() {
      cc.preInitializeObject(this);
      this.rasterResult_ = undefined;
    },

    initialize: function() {
      if (!this.args.params.layerRect)
        throw new Error('Missing layer rect');
      this.layerRect_ = this.args.params.layerRect;
    },

    get layerRect() {
      return this.layerRect_;
    },

    get guid() {
      return this.guid_;
    },

    getBase64SkpData: function() {
      return this.args.skp64;
    },

    getOps: function() {
      if (!PictureSnapshot.CanGetOps()) {
        console.error(PictureSnapshot.HowToEnablePictureDebugging());
        return undefined;
      }

      var ops = window.chrome.skiaBenchmarking.getOps({
        skp64: this.args.skp64,
        params: {
          layer_rect: this.args.params.layerRect.toArray(),
          opaque_rect: this.args.params.opaqueRect.toArray()
        }
      });

      if (!ops)
        console.error('Failed to get picture ops.');

      return ops;
    },

    getOpTimings: function() {
      if (!PictureSnapshot.CanGetOpTimings()) {
        console.error(PictureSnapshot.HowToEnablePictureDebugging());
        return undefined;
      }

      var opTimings = window.chrome.skiaBenchmarking.getOpTimings({
        skp64: this.args.skp64,
        params: {
          layer_rect: this.args.params.layerRect.toArray(),
          opaque_rect: this.args.params.opaqueRect.toArray()
        }
      });

      if (!opTimings)
        console.error('Failed to get picture op timings.');

      return opTimings;
    },

    /**
     * Tag each op with the time it takes to rasterize.
     *
     * FIXME: We should use real statistics to get better numbers here, see
     *        https://code.google.com/p/trace-viewer/issues/detail?id=357
     *
     * @param {Array} ops Array of Skia operations.
     * @return {Array} Skia ops where op.cmd_time contains the associated time
     *         for a given op.
     */
    tagOpsWithTimings: function(ops) {

      var opTimings = new Array();
      for (var iteration = 0; iteration < OPS_TIMING_ITERATIONS; iteration++) {
        opTimings[iteration] = this.getOpTimings();
        if (!opTimings[iteration] || !opTimings[iteration].cmd_times)
          return ops;
        if (opTimings[iteration].cmd_times.length != ops.length)
          return ops;
      }

      for (var opIndex = 0; opIndex < ops.length; opIndex++) {
        var average = 0;
        for (var i = 0; i < OPS_TIMING_ITERATIONS; i++)
          average += opTimings[i].cmd_times[opIndex];
        average /= OPS_TIMING_ITERATIONS;
        ops[opIndex].cmd_time = average;
      }

      return ops;
    },

    /**
     * Rasterize the picture.
     *
     * @param {{opt_stopIndex: number, params}} The SkPicture operation to
     *     rasterize up to. If not defined, the entire SkPicture is rasterized.
     * @param {{opt_showOverdraw: bool, params}} Defines whether pixel overdraw
           should be visualized in the image.
     * @param {function(cc.PictureAsImageData)} The callback function that is
     *     called after rasterization is complete or fails.
     */
    rasterize: function(params, rasterCompleteCallback) {
      if (!PictureSnapshot.CanRasterize() || !PictureSnapshot.CanGetOps()) {
        rasterCompleteCallback(new cc.PictureAsImageData(
            this, cc.PictureSnapshot.HowToEnablePictureDebugging()));
        return;
      }

      var raster = window.chrome.skiaBenchmarking.rasterize(
          {
            skp64: this.args.skp64,
            params: {
              layer_rect: this.args.params.layerRect.toArray(),
              opaque_rect: this.args.params.opaqueRect.toArray()
            }
          },
          {
            stop: params.stopIndex === undefined ? -1 : params.stopIndex,
            overdraw: !!params.showOverdraw,
            params: { }
          });

      if (raster) {
        var canvas = document.createElement('canvas');
        var ctx = canvas.getContext('2d');
        canvas.width = raster.width;
        canvas.height = raster.height;
        var imageData = ctx.createImageData(raster.width, raster.height);
        imageData.data.set(new Uint8ClampedArray(raster.data));
        rasterCompleteCallback(new cc.PictureAsImageData(this, imageData));
      } else {
        var error = 'Failed to rasterize picture. ' +
                'Your recording may be from an old Chrome version. ' +
                'The SkPicture format is not backward compatible.';
        rasterCompleteCallback(new cc.PictureAsImageData(this, error));
      }
    }
  };

  ObjectSnapshot.register('cc::Picture', PictureSnapshot);

  return {
    PictureSnapshot: PictureSnapshot
  };
});
