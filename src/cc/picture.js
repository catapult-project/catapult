// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.guid');
base.require('base.rect');
base.require('base.raf');
base.require('tracing.trace_model.object_instance');
base.require('cc.picture_as_canvas');
base.require('cc.util');

base.exportTo('cc', function() {

  var ObjectSnapshot = tracing.trace_model.ObjectSnapshot;

  // Number of pictures created. Used as an uniqueId because we are immutable.
  var PictureCount = 0;

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
      return 'Your chrome is old, skiaBenchmarking.getOps not found';
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
      this.layerRect_ = base.Rect.FromArray(this.layerRect_);
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
          layer_rect: this.args.params.layerRect,
          opaque_rect: this.args.params.opaqueRect
        }
      });

      if (!ops)
        console.error('Failed to get picture ops.');

      return ops;
    },

    /**
     * Rasterize the picture.
     *
     * @param {{opt_stopIndex: number, params}} The SkPicture operation to
     *     rasterize up to. If not defined, the entire SkPicture is rasterized.
     * @param {function(cc.PictureAsCanvas)} The callback function that is
     *     called after rasterization is complete or fails.
     */
    rasterize: function(params, rasterCompleteCallback) {
      if (!PictureSnapshot.CanRasterize() || !PictureSnapshot.CanGetOps()) {
        rasterCompleteCallback(new cc.PictureAsCanvas(
            this, cc.PictureSnapshot.HowToEnablePictureDebugging()));
        return;
      }

      var raster = window.chrome.skiaBenchmarking.rasterize(
          {
            skp64: this.args.skp64,
            params: {
              layer_rect: this.args.params.layerRect,
              opaque_rect: this.args.params.opaqueRect
            }
          },
          {
            stop: params.stopIndex === undefined ? -1 : params.stopIndex,
            params: { }
          });

      if (raster) {
        var canvas = document.createElement('canvas');
        var ctx = canvas.getContext('2d');
        canvas.width = raster.width;
        canvas.height = raster.height;
        var imageData = ctx.createImageData(raster.width, raster.height);
        imageData.data.set(new Uint8ClampedArray(raster.data));
        ctx.putImageData(imageData, 0, 0);
        rasterCompleteCallback(new cc.PictureAsCanvas(this, canvas));
      } else {
        var error = 'Failed to rasterize picture. ' +
                'Your recording may be from an old Chrome version. ' +
                'The SkPicture format is not backward compatible.';
        rasterCompleteCallback(new cc.PictureAsCanvas(this, error));
      }
    }
  };

  ObjectSnapshot.register('cc::Picture', PictureSnapshot);

  return {
    PictureSnapshot: PictureSnapshot
  };
});
