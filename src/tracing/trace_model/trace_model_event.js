// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.guid');

/**
 * @fileoverview Provides the TraceModelEvent class.
 */
base.exportTo('tracing.trace_model', function() {
  /**
   * A TraceModelEvent represents the basic set of information collected for
   * each type of event in the system.
   *
   * All time units are stored in milliseconds.
   * @constructor
   */
  function TraceModelEvent(category, title, colorId, start, args) {
    this.guid_ = base.GUID.allocate();
    this.category = category || '';
    this.title = title;
    this.colorId = colorId;
    this.start = start;
    this.args = args;

    this.didNotFinish = false;
  }

  TraceModelEvent.prototype = {
    selected: false,

    duration: 0,

    get end() {
      return this.start;
    },

    get guid() {
      return this.guid_;
    }
  };

  return {
    TraceModelEvent: TraceModelEvent
  };
});

