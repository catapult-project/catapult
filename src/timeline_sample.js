// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the TimelineSample class.
 */
base.exportTo('tracing', function() {

  /**
   * A TimelineSample represents a sample taken at an instant in time
   * plus parameters associated with that sample.
   *
   * NOTE: The TimelineSample class implements the same interface as
   * TimelineSlice. These must be kept in sync.
   *
   * All time units are stored in milliseconds.
   * @constructor
   */
  function TimelineSample(category, title, colorId, ts, args) {
    this.category = category || '';
    this.title = title;
    this.colorId = colorId;
    this.start = ts;
    this.args = args;
  }

  TimelineSample.prototype = {
    selected: false,

    duration: 0,

    get end() {
      return this.start;
    }
  };

  return {
    TimelineSample: TimelineSample
  };
});
