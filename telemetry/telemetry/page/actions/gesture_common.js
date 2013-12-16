// Copyright 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// This file provides common functionality for synthetic gesture actions.
'use strict';

(function() {

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

  window.__GestureCommon_GetBoundingVisibleRect = getBoundingVisibleRect;
})();
