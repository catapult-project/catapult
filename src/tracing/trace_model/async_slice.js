// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.trace_model.slice');

/**
 * @fileoverview Provides the AsyncSlice class.
 */
base.exportTo('tracing.trace_model', function() {
  /**
   * A AsyncSlice represents an interval of time during which an
   * asynchronous operation is in progress. An AsyncSlice consumes no CPU time
   * itself and so is only associated with Threads at its start and end point.
   *
   * @constructor
   */
  function AsyncSlice(category, title, colorId, start, args) {
    tracing.trace_model.Slice.apply(this, arguments);
  };

  AsyncSlice.prototype = {
    __proto__: tracing.trace_model.Slice.prototype,

    toJSON: function() {
      var obj = new Object();
      var keys = Object.keys(this);
      for (var i = 0; i < keys.length; i++) {
        var key = keys[i];
        if (typeof this[key] == 'function')
          continue;
        if (key == 'startThread' || key == 'endThread') {
          obj[key] = this[key].guid;
          continue;
        }
        obj[key] = this[key];
      }
      return obj;
    },

    id: undefined,

    startThread: undefined,

    endThread: undefined,

    subSlices: undefined
  };

  return {
    AsyncSlice: AsyncSlice
  };
});
