// Copyright 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// This file provides the ScrollAction object, which scrolls a page
// to the bottom or for a specified distance:
//   1. var action = new __ScrollAction(callback, opt_distance_func)
//   2. action.start(scroll_options)
'use strict';

(function() {
  var MAX_SCROLL_LENGTH_TIME_MS = 6250;

  function ScrollGestureOptions(opt_options) {
    if (opt_options) {
      this.element_ = opt_options.element;
      this.leftStartRatio_ = opt_options.left_start_ratio;
      this.topStartRatio_ = opt_options.top_start_ratio;
      this.direction_ = opt_options.direction;
      this.speed_ = opt_options.speed;
      this.gesture_source_type_ = opt_options.gesture_source_type;
    } else {
      this.element_ = document.scrollingElement || document.body;
      this.leftStartRatio_ = 0.5;
      this.topStartRatio_ = 0.5;
      this.direction_ = 'down';
      this.speed_ = 800;
      this.gesture_source_type_ = chrome.gpuBenchmarking.DEFAULT_INPUT;
    }
  }

  function supportedByBrowser() {
    return !!(window.chrome &&
              chrome.gpuBenchmarking &&
              chrome.gpuBenchmarking.smoothScrollBy &&
              chrome.gpuBenchmarking.visualViewportHeight &&
              chrome.gpuBenchmarking.visualViewportWidth);
  }

  // This class scrolls a page from the top to the bottom once.
  //
  // The page is scrolled down by a single scroll gesture.
  function ScrollAction(opt_callback, opt_distanceFunc) {
    var self = this;

    this.beginMeasuringHook = function() {};
    this.endMeasuringHook = function() {};

    this.callback_ = opt_callback;
    this.distance_func_ = opt_distanceFunc;
  }

  ScrollAction.prototype.getScrollDistanceDown_ = function() {
    var clientHeight;
    // clientHeight is "special" for the body element.
    if (this.element_ === document.body)
      clientHeight = __GestureCommon_GetWindowHeight();
    else
      clientHeight = this.element_.clientHeight;

    return this.element_.scrollHeight -
           this.element_.scrollTop -
           clientHeight;
  };

  ScrollAction.prototype.getScrollDistanceUp_ = function() {
    return this.element_.scrollTop;
  };

  ScrollAction.prototype.getScrollDistanceRight_ = function() {
    var clientWidth;
    // clientWidth is "special" for the body element.
    if (this.element_ === document.body)
      clientWidth = __GestureCommon_GetWindowWidth();
    else
      clientWidth = this.element_.clientWidth;

    return this.element_.scrollWidth - this.element_.scrollLeft - clientWidth;
  };

  ScrollAction.prototype.getScrollDistanceLeft_ = function() {
    return this.element_.scrollLeft;
  };

  ScrollAction.prototype.getScrollDistance_ = function() {
    if (this.distance_func_)
      return this.distance_func_();

    if (this.options_.direction_ === 'down') {
      return this.getScrollDistanceDown_();
    } else if (this.options_.direction_ === 'up') {
      return this.getScrollDistanceUp_();
    } else if (this.options_.direction_ === 'right') {
      return this.getScrollDistanceRight_();
    } else if (this.options_.direction_ === 'left') {
      return this.getScrollDistanceLeft_();
    } else if (this.options_.direction_ === 'upleft') {
      return Math.min(this.getScrollDistanceUp_(),
                      this.getScrollDistanceLeft_());
    } else if (this.options_.direction_ === 'upright') {
      return Math.min(this.getScrollDistanceUp_(),
                      this.getScrollDistanceRight_());
    } else if (this.options_.direction_ === 'downleft') {
      return Math.min(this.getScrollDistanceDown_(),
                      this.getScrollDistanceLeft_());
    } else if (this.options_.direction_ === 'downright') {
      return Math.min(this.getScrollDistanceDown_(),
                      this.getScrollDistanceRight_());
    }
  };

  ScrollAction.prototype.start = function(opt_options) {
    this.options_ = new ScrollGestureOptions(opt_options);
    // Assign this.element_ here instead of constructor, because the constructor
    // ensures this method will be called after the document is loaded.
    this.element_ = this.options_.element_;

    // Calculate scroll point.
    var rect = __GestureCommon_GetBoundingVisibleRect(this.options_.element_);
    this.startLeft = rect.left + rect.width * this.options_.leftStartRatio_;
    this.startTop = rect.top + rect.height * this.options_.topStartRatio_;

    if (rect.width === 0 || rect.height === 0) {
      throw new Error('Scroll element has zero height and/or width.');
    }

    requestAnimationFrame(this.startGesture_.bind(this));
  };

  ScrollAction.prototype.startGesture_ = function() {
    this.beginMeasuringHook();

    var maxScrollLengthPixels = (MAX_SCROLL_LENGTH_TIME_MS / 1000) *
        this.options_.speed_;
    var distance = Math.min(maxScrollLengthPixels, this.getScrollDistance_());

   chrome.gpuBenchmarking.smoothScrollBy(
        distance, this.onGestureComplete_.bind(this),
        this.startLeft, this.startTop, this.options_.gesture_source_type_,
        this.options_.direction_, this.options_.speed_);
  };

  ScrollAction.prototype.onGestureComplete_ = function() {
    this.endMeasuringHook();

    // We're done.
    if (this.callback_)
      this.callback_();
  };

  window.__ScrollAction = ScrollAction;
  window.__ScrollAction_SupportedByBrowser = supportedByBrowser;
})();
