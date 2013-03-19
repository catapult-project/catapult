// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Model is a parsed representation of the
 * TraceEvents obtained from base/trace_event in which the begin-end
 * tokens are converted into a hierarchy of processes, threads,
 * subrows, and slices.
 *
 * The building block of the model is a slice. A slice is roughly
 * equivalent to function call executing on a specific thread. As a
 * result, slices may have one or more subslices.
 *
 * A thread contains one or more subrows of slices. Row 0 corresponds to
 * the "root" slices, e.g. the topmost slices. Row 1 contains slices that
 * are nested 1 deep in the stack, and so on. We use these subrows to draw
 * nesting tasks.
 *
 */
'use strict';
base.exportTo('base', function() {

  function Range() {
    this.isEmpty_ = true;
    this.min_ = undefined;
    this.max_ = undefined;
  };

  Range.prototype = {
    __proto__: Object.prototype,

    reset: function() {
      this.isEmpty_ = true;
      this.min_ = undefined;
      this.max_ = undefined;
    },

    get isEmpty() {
      return this.isEmpty_;
    },

    addRange: function(range) {
      if (range.isEmpty)
        return;
      this.addValue(range.min);
      this.addValue(range.max);
    },

    addValue: function(value) {
      if (this.isEmpty_) {
        this.max_ = value;
        this.min_ = value;
        this.isEmpty_ = false;
        return;
      }
      this.max_ = Math.max(this.max_, value);
      this.min_ = Math.min(this.min_, value);
    },

    get min() {
      if (this.isEmpty_)
        return undefined;
      return this.min_;
    },

    get max() {
      if (this.isEmpty_)
        return undefined;
      return this.max_;
    },
  };

  return {
    Range: Range
  };

});
