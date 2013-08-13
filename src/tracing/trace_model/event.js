// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.guid');

/**
 * @fileoverview Provides the Event class.
 */
base.exportTo('tracing.trace_model', function() {
  /**
   * A Event is the base type for any non-container, selectable piece
   * of data in the trace model.
   *
   * @constructor
   */
  function Event() {
    this.guid_ = base.GUID.allocate();
    this.selected = false;
  }

  Event.prototype = {
    get guid() {
      return this.guid_;
    }
  };

  return {
    Event: Event
  };
});
