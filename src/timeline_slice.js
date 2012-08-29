// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the TimelineSlice class.
 */
base.exportTo('tracing', function() {

  /**
   * A TimelineSlice represents an interval of time plus parameters associated
   * with that interval.
   *
   * All time units are stored in milliseconds.
   * @constructor
   */
  function TimelineSlice(category, title, colorId, start, args, opt_duration) {
    this.category = category || '';
    this.title = title;
    this.start = start;
    this.colorId = colorId;
    this.args = args;
    this.didNotFinish = false;
    if (opt_duration !== undefined)
      this.duration = opt_duration;
  }

  TimelineSlice.prototype = {
    selected: false,

    duration: undefined,

    get end() {
      return this.start + this.duration;
    }
  };

  return {
    TimelineSlice: TimelineSlice
  };
});
