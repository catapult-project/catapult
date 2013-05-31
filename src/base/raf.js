// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.exportTo('base', function() {
  var pendingPreAFs = [];
  var pendingRAFs = [];
  var currentRAFDispatchList = undefined;

  var rafScheduled = false;
  function scheduleRAF() {
    if (rafScheduled)
      return;
    rafScheduled = true;
    window.webkitRequestAnimationFrame(processRequests);
  }

  function processRequests() {
    rafScheduled = false;
    var currentPreAFs = pendingPreAFs;
    var currentRAFs = pendingRAFs;
    pendingPreAFs = [];
    pendingRAFs = [];
    for (var i = 0; i < pendingPreAFs; i++)
      this.pendingPreAFs.callback.call(pendingPreAFs.context);

    currentRAFDispatchList = currentRAFs;
    while (currentRAFDispatchList.length > 0) {
      var task = currentRAFDispatchList.shift();
      try {
        task.callback.call(task.context);
      } catch (e) {
        console.error(e);
      }
    }
    currentRAFDispatchList = undefined;
  }

  function requestPreAnimationFrame(callback, opt_this) {
    scheduleRAF();
    pendingRAFs.push({
      callback: callback,
      context: opt_this || window});
  }

  function requestAnimationFrameInThisFrameIfPossible(callback, opt_this) {
    if (!currentRAFDispatchList) {
      requestAnimationFrame(callback, opt_this);
      return;
    }
    currentRAFDispatchList.push({
      callback: callback,
      context: opt_this || window});
    return;
  }

  function requestAnimationFrame(callback, opt_this) {
    scheduleRAF();
    pendingRAFs.push({
      callback: callback,
      context: opt_this || window});
  }
  return {
    requestPreAnimationFrame: requestPreAnimationFrame,
    requestAnimationFrame: requestAnimationFrame,
    requestAnimationFrameInThisFrameIfPossible:
        requestAnimationFrameInThisFrameIfPossible
  };
});
