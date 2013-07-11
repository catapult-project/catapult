// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Helper functions for use in tracing tests.
 */
'use strict';

base.require('tracing.trace_model.counter');
base.require('tracing.trace_model.slice');
base.require('tracing.trace_model.slice_group');

base.exportTo('tracing.test_utils', function() {
  function newAsyncSlice(start, duration, startThread, endThread) {
    return newAsyncSliceNamed('a', start, duration, startThread, endThread);
  }

  function newAsyncSliceNamed(name, start, duration, startThread, endThread) {
    var s = new tracing.trace_model.AsyncSlice('', name, 0, start);
    s.duration = duration;
    s.startThread = startThread;
    s.endThread = endThread;
    var subSlice = new tracing.trace_model.AsyncSlice('', name, 0, start);
    subSlice.duration = duration;
    subSlice.startThread = startThread;
    subSlice.endThread = endThread;
    s.subSlices = [subSlice];
    return s;
  }

  function newCounter(parent) {
    return newCounterNamed(parent, 'a');
  }

  function newCounterNamed(parent, name) {
    var s = new tracing.trace_model.Counter(parent, name, null, name);
    return s;
  }

  function newCounterCategory(parent, category, name) {
    var s = new tracing.trace_model.Counter(parent, name, category, name);
    return s;
  }

  function newSlice(start, duration) {
    return newSliceNamed('a', start, duration);
  }

  function newSliceNamed(name, start, duration) {
    var s = new tracing.trace_model.Slice('', name, 0, start, {}, duration);
    return s;
  }

  function newSliceCategory(category, name, start, duration) {
    var s = new tracing.trace_model.Slice(
        category, name, 0, start, {}, duration);
    return s;
  }

  function findSliceNamed(slices, name) {
    if (slices instanceof tracing.trace_model.SliceGroup)
      slices = slices.slices;
    for (var i = 0; i < slices.length; i++)
      if (slices[i].title == name)
        return slices[i];
      return undefined;
  }

  return {
    newAsyncSlice: newAsyncSlice,
    newAsyncSliceNamed: newAsyncSliceNamed,
    newCounter: newCounter,
    newCounterNamed: newCounterNamed,
    newCounterCategory: newCounterCategory,
    newSlice: newSlice,
    newSliceNamed: newSliceNamed,
    newSliceCategory: newSliceCategory,
    findSliceNamed: findSliceNamed
  };
});
