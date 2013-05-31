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

  function runTask(task) {
    try {
      task.callback.call(task.context);
    } catch (e) {
      if (e.message)
        console.error(e.message, e.stack);
      else
        console.error(e);
    }
  }

  function processRequests() {
    rafScheduled = false;

    var currentPreAFs = pendingPreAFs;
    currentRAFDispatchList = pendingRAFs;
    pendingPreAFs = [];
    pendingRAFs = [];
    for (var i = 0; i < currentPreAFs.length; i++)
      runTask(currentPreAFs[i]);

    while (currentRAFDispatchList.length > 0)
      runTask(currentRAFDispatchList.shift());
    currentRAFDispatchList = undefined;
  }

  function requestPreAnimationFrame(callback, opt_this) {
    scheduleRAF();
    pendingPreAFs.push({
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
