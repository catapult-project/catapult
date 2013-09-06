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
   * The SelectionState enum defines how Events are displayed in the view.
   */
  var SelectionState = {
    NONE: 0,
    SELECTED: 1,
    HIGHLIGHTED: 2,
    DIMMED: 3
  };

  /**
   * A Event is the base type for any non-container, selectable piece
   * of data in the trace model.
   *
   * @constructor
   */
  function Event() {
    this.guid_ = base.GUID.allocate();
    this.selectionState = SelectionState.NONE;
  }

  Event.prototype = {
    get guid() {
      return this.guid_;
    },

    get selected() {
      return this.selectionState === SelectionState.SELECTED;
    }
  };

  return {
    Event: Event,
    SelectionState: SelectionState
  };
});
