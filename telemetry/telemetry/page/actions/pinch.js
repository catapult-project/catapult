// Copyright 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// This file provides the PinchAction object, which zooms into or out of a
// page by a given scale factor:
//   1. var action = new __PinchAction(callback)
//   2. action.start(pinch_options)
'use strict';

(function() {

  function supportedByBrowser() {
    return !!(window.chrome &&
              chrome.gpuBenchmarking &&
              chrome.gpuBenchmarking.pinchBy);
  }

  /**
    * Performs a single vertical pinch gesture to zoom in or out, anchored
    * in the center of the window.
    * Only works if pinchBy gesture is available.
    * @constructor
    */
  function PinchGesture(zoom_in) {
    this.zoom_in_ = zoom_in;
  };

  PinchGesture.prototype.start = function(pixels_to_move, callback) {
    this.callback_ = callback;

    // The anchor point of the gesture is the center of the window.
    var anchor_x = window.innerWidth / 2;
    var anchor_y = window.innerHeight / 2;

    chrome.gpuBenchmarking.pinchBy(this.zoom_in_, pixels_to_move,
                                   anchor_x, anchor_y,
                                   function() { callback(); });
  };

  // This class zooms into or out of a page, given a number of pixels for
  // the synthetic pinch gesture to cover.
  function PinchAction(opt_callback) {
    var self = this;

    this.beginMeasuringHook = function() {}
    this.endMeasuringHook = function() {}

    this.callback_ = opt_callback;
  };

  PinchAction.prototype.start = function(zoom_in, pixels_to_move) {
    this.zoom_in_ = zoom_in;
    this.pixels_to_move_ = pixels_to_move;

    requestAnimationFrame(this.startPass_.bind(this));
  };

  PinchAction.prototype.startPass_ = function() {
    this.beginMeasuringHook();

    this.gesture_ = new PinchGesture(this.zoom_in_);
    this.gesture_.start(this.pixels_to_move_,
                        this.onGestureComplete_.bind(this));
  };

  PinchAction.prototype.onGestureComplete_ = function() {
    this.endMeasuringHook();

    if (this.callback_)
      this.callback_();
  };

  window.__PinchAction = PinchAction;
  window.__PinchAction_SupportedByBrowser = supportedByBrowser;
})();
