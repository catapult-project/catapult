// Copyright 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// This file provides common functionality for synthetic gesture actions.
'use strict';

(function() {

  // Make sure functions are injected only once.
  if (window.__GestureCommon_GetBoundingVisibleRect)
    return;

  // Returns the bounding rectangle wrt to the top-most document.
  function getBoundingRect(el) {
    var client_rect = el.getBoundingClientRect();
    var bound = { left: client_rect.left,
                  top: client_rect.top,
                  width: client_rect.width,
                  height: client_rect.height };

    var frame = el.ownerDocument.defaultView.frameElement;
    while (frame) {
      var frame_bound = frame.getBoundingClientRect();
      // This computation doesn't account for more complex CSS transforms on the
      // frame (e.g. scaling or rotations).
      bound.left += frame_bound.left;
      bound.top += frame_bound.top;

      frame = frame.ownerDocument.frameElement;
    }
    return bound;
  }

  // TODO(ulan): Remove this function once
  // chrome.gpuBenchmarking.pageScaleFactor is available in reference builds.
  function getPageScaleFactor() {
    if (chrome.gpuBenchmarking.pageScaleFactor)
      return chrome.gpuBenchmarking.pageScaleFactor();
    return 1;
  }

  // Zoom-independent window height. See crbug.com/627123 for more details.
  function getWindowHeight() {
    return getPageScaleFactor() * chrome.gpuBenchmarking.visualViewportHeight();
  }

  // Zoom-independent window width. See crbug.com/627123 for more details.
  function getWindowWidth() {
    return getPageScaleFactor() * chrome.gpuBenchmarking.visualViewportWidth();
  }

  function getBoundingVisibleRect(el) {
    var rect = getBoundingRect(el);
    if (rect.top < 0) {
      rect.height += rect.top;
      rect.top = 0;
    }
    if (rect.left < 0) {
      rect.width += rect.left;
      rect.left = 0;
    }

    var windowHeight = getWindowHeight();
    var windowWidth = getWindowWidth();
    var outsideHeight = (rect.top + rect.height) - windowHeight;
    var outsideWidth = (rect.left + rect.width) - windowWidth;

    if (outsideHeight > 0) {
      rect.height -= outsideHeight;
    }
    if (outsideWidth > 0) {
      rect.width -= outsideWidth;
    }
    return rect;
  };

  window.__GestureCommon_GetBoundingVisibleRect = getBoundingVisibleRect;
  window.__GestureCommon_GetWindowHeight = getWindowHeight;
  window.__GestureCommon_GetWindowWidth = getWindowWidth;
})();
