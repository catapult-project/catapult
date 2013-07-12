// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.utils');

base.exportTo('base', function() {
  // Setting this to true will cause stack traces to get dumped into the
  // tasks. When an exception happens the original stack will be printed.
  //
  // NOTE: This should never be set committed as true.
  var recordRAFStacks = false;

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

  function onAnimationFrameError(e, opt_stack) {
    if (opt_stack)
      console.log(opt_stack);

    if (e.message)
      console.error(e.message, e.stack);
    else
      console.error(e);
  }

  function runTask(task) {
    try {
      task.callback.call(task.context);
    } catch (e) {
      base.onAnimationFrameError(e, task.stack);
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

  function getStack_() {
    if (!recordRAFStacks)
      return '';

    var stackLines = base.stackTrace();
    // Strip off getStack_.
    stackLines.shift();
    return stackLines.join('\n');
  }

  function requestPreAnimationFrame(callback, opt_this) {
    pendingPreAFs.push({
      callback: callback,
      context: opt_this || window,
      stack: getStack_()});
    scheduleRAF();
  }

  function requestAnimationFrameInThisFrameIfPossible(callback, opt_this) {
    if (!currentRAFDispatchList) {
      requestAnimationFrame(callback, opt_this);
      return;
    }
    currentRAFDispatchList.push({
      callback: callback,
      context: opt_this || window,
      stack: getStack_()});
    return;
  }

  function requestAnimationFrame(callback, opt_this) {
    pendingRAFs.push({
      callback: callback,
      context: opt_this || window,
      stack: getStack_()});
    scheduleRAF();
  }
  return {
    onAnimationFrameError: onAnimationFrameError,
    requestPreAnimationFrame: requestPreAnimationFrame,
    requestAnimationFrame: requestAnimationFrame,
    requestAnimationFrameInThisFrameIfPossible:
        requestAnimationFrameInThisFrameIfPossible
  };
});
