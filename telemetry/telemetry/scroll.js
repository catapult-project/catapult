// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Inject this script on any page to measure framerate as the page is scrolled
// from top to bottom.
//
// Usage:
//   1. Define a callback that takes a RenderingStats object as a parameter.
//   2. To start the test, call new __ScrollTest(callback).
//   3a. When the test is complete, the callback will be called.
//   3b. If no callback is specified, the results is sent to the console.

(function() {
  MAX_SCROLL_LENGTH_PIXELS = 5000;

  var getTimeMs = (function() {
    if (window.performance)
      return (performance.now       ||
              performance.mozNow    ||
              performance.msNow     ||
              performance.oNow      ||
              performance.webkitNow).bind(window.performance);
    else
      return function() { return new Date().getTime(); };
  })();

  var requestAnimationFrame = (function() {
    return window.requestAnimationFrame       ||
           window.webkitRequestAnimationFrame ||
           window.mozRequestAnimationFrame    ||
           window.oRequestAnimationFrame      ||
           window.msRequestAnimationFrame     ||
           function(callback) {
             window.setTimeout(callback, 1000 / 60);
           };
  })().bind(window);

  /**
   * Scrolls a given element down a certain amount to emulate user scrolling.
   * Uses smooth scrolling capabilities provided by the platform, if available.
   * @constructor
   */
  function SmoothScrollDownGesture(opt_element) {
    this.element_ = opt_element || document.body;
  };

  function min(a, b) {
    if (a > b) {
      return b;
    }
    return a;
  };

  function getBoundingVisibleRect(el) {
    var bound = el.getBoundingClientRect();
    var rect = { top: bound.top,
                 left: bound.left,
                 width: bound.width,
                 height: bound.height };
    var outsideHeight = (rect.top + rect.height) - window.innerHeight;
    var outsideWidth = (rect.left + rect.width) - window.innerWidth;

    if (outsideHeight > 0) {
      rect.height -= outsideHeight;
    }
    if (outsideWidth > 0) {
      rect.width -= outsideWidth;
    }
    return rect;
  };

  SmoothScrollDownGesture.prototype.start = function(distance, callback) {
    this.callback_ = callback;
    if (chrome &&
        chrome.gpuBenchmarking &&
        chrome.gpuBenchmarking.smoothScrollBy) {
      var rect = getBoundingVisibleRect(this.element_);
      chrome.gpuBenchmarking.smoothScrollBy(distance, function() {
        callback();
      }, rect.left + rect.width / 2, rect.top + rect.height / 2);
      return;
    }

    var SCROLL_DELTA = 100;
    this.element_.scrollTop += SCROLL_DELTA;
    requestAnimationFrame(callback);
  };

  /**
   * Tracks rendering performance using the gpuBenchmarking.renderingStats API.
   * @constructor
   */
  function GpuBenchmarkingRenderingStats() {
  }

  GpuBenchmarkingRenderingStats.prototype.start = function() {
    this.initialStats_ = this.getRenderingStats_();
  }
  GpuBenchmarkingRenderingStats.prototype.stop = function() {
    this.finalStats_ = this.getRenderingStats_();
  }

  GpuBenchmarkingRenderingStats.prototype.getDeltas = function() {
    if (!this.initialStats_)
      throw new Error('Start not called.');

    if (!this.finalStats_)
      throw new Error('Stop was not called.');

    var stats = this.finalStats_;
    for (var key in stats)
      stats[key] -= this.initialStats_[key];
    return stats;
  };

  GpuBenchmarkingRenderingStats.prototype.getRenderingStats_ = function() {
    var stats = chrome.gpuBenchmarking.renderingStats();
    stats.totalTimeInSeconds = getTimeMs() / 1000;
    return stats;
  };

  /**
   * Tracks rendering performance using requestAnimationFrame.
   * @constructor
   */
  function RafRenderingStats() {
    this.recording_ = false;
    this.frameTimes_ = [];
  }

  RafRenderingStats.prototype.start = function() {
    if (this.recording_)
      throw new Error('Already started.');
    this.recording_ = true;
    requestAnimationFrame(this.recordFrameTime_.bind(this));
  }

  RafRenderingStats.prototype.stop = function() {
    this.recording_ = false;
  }

  RafRenderingStats.prototype.getDeltas = function() {
    var results = {};
    results.numAnimationFrames = this.frameTimes_.length - 1;
    results.numFramesSentToScreen = results.numAnimationFrames;
    results.droppedFrameCount = this.getDroppedFrameCount_(this.frameTimes_);
    results.totalTimeInSeconds = (
        this.frameTimes_[this.frameTimes_.length - 1] -
        this.frameTimes_[0]) / 1000;
    return results;
  };

  RafRenderingStats.prototype.recordFrameTime_ = function(timestamp) {
    if (!this.recording_)
      return;

    this.frameTimes_.push(timestamp);
    requestAnimationFrame(this.recordFrameTime_.bind(this));
  };

  RafRenderingStats.prototype.getDroppedFrameCount_ = function(frameTimes) {
    var droppedFrameCount = 0;
    for (var i = 1; i < frameTimes.length; i++) {
      var frameTime = frameTimes[i] - frameTimes[i-1];
      if (frameTime > 1000 / 55)
        droppedFrameCount++;
    }
    return droppedFrameCount;
  };

  // This class scrolls a page from the top to the bottom once.
  //
  // The page is scrolled down by a set of scroll gestures. These gestures
  // correspond to a reading gesture on that platform.
  //
  // start -> startPass_ -> ...scrolling... -> onGestureComplete_ ->
  //       -> startPass_ -> .. scrolling... -> onGestureComplete_ -> callback_
  function ScrollTest(opt_callback) {
    var self = this;

    this.callback_ = opt_callback;
  }

  ScrollTest.prototype.getRemainingScrollDistance_ = function() {
    var clientHeight;
    // clientHeight is "special" for the body element.
    if (this.element_ == document.body)
      clientHeight = window.innerHeight;
    else
      clientHeight = this.element_.clientHeight;

    return this.scrollHeight_ - this.element_.scrollTop - clientHeight;
  }

  ScrollTest.prototype.start = function(opt_element) {
    // Assign this.element_ here instead of constructor, because the constructor
    // ensures this method will be called after the document is loaded.
    this.element_ = opt_element || document.body;
    // Some pages load more content when you scroll to the bottom. Record
    // the original element height here and only scroll to that point.
    // -1 to allow for rounding errors on scaled viewports (like mobile).
    this.scrollHeight_ = Math.min(MAX_SCROLL_LENGTH_PIXELS,
                                  this.element_.scrollHeight - 1);
    requestAnimationFrame(this.startPass_.bind(this));
  };

  ScrollTest.prototype.startPass_ = function() {
    this.element_.scrollTop = 0;
    if (window.chrome && chrome.gpuBenchmarking &&
        chrome.gpuBenchmarking.renderingStats)
      this.renderingStats_ = new GpuBenchmarkingRenderingStats();
    else
      this.renderingStats_ = new RafRenderingStats();
    this.renderingStats_.start();

    this.gesture_ = new SmoothScrollDownGesture(this.element_);
    this.gesture_.start(this.getRemainingScrollDistance_(),
                        this.onGestureComplete_.bind(this));
  };

  ScrollTest.prototype.onGestureComplete_ = function(timestamp) {
    // If the scrollHeight went down, only scroll to the new scrollHeight.
    // -1 to allow for rounding errors on scaled viewports (like mobile).
    this.scrollHeight_ = Math.min(this.scrollHeight_,
                                  this.element_.scrollHeight - 1);

    if (this.getRemainingScrollDistance_() > 0) {
      this.gesture_.start(this.getRemainingScrollDistance_(),
                          this.onGestureComplete_.bind(this));
      return;
    }

    this.endPass_();

    // We're done.
    if (this.callback_)
      this.callback_(this.renderingStats_.getDeltas());
    else
      console.log(this.renderingStats_.getDeltas());
  };

  ScrollTest.prototype.endPass_ = function() {
    this.renderingStats_.stop();
  };

  window.__ScrollTest = ScrollTest;
  window.__ScrollTest_GetBoundingVisibleRect = getBoundingVisibleRect;
})();
