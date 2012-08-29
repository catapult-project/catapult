// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview TimelineModel is a parsed representation of the
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
base.exportTo('tracing', function() {

  function filterSliceArray(filter, slices) {
    if (filter === undefined)
      return slices;

    var matched = [];
    for (var i = 0; i < slices.length; ++i) {
      if (filter.matchSlice(slices[i]))
        matched.push(slices[i]);
    }
    return matched;
  }

  /**
   * @constructor The generic base class for filtering a TimelineModel based on
   * various rules. The base class returns true for everything.
   */
  function TimelineFilter() {
  }

  TimelineFilter.prototype = {
    __proto__: Object.prototype,

    matchCounter: function(counter) {
      return true;
    },

    matchCpu: function(cpu) {
      return true;
    },

    matchProcess: function(process) {
      return true;
    },

    matchSlice: function(slice) {
      return true;
    },

    matchThread: function(thread) {
      return true;
    }
  };

  /**
   * @constructor A filter that matches objects by their name.
   * Timeline.findAllObjectsMatchingFilter
   */
  function TimelineTitleFilter(text) {
    TimelineFilter.call(this);
    this.text_ = text;
  }
  TimelineTitleFilter.prototype = {
    __proto__: TimelineFilter.prototype,

    matchSlice: function(slice) {
      if (this.text_.length == 0)
        return false;
      if (slice.title === undefined)
        return false;
      return slice.title.indexOf(this.text_) != -1;
    }
  };

  /**
   * @constructor A filter that filters objects by their category.
   * Objects match if they are NOT in the list of categories
   * @param {Array<string>} opt_categories Categories to blacklist.
   */
  function TimelineCategoryFilter(opt_categories) {
    TimelineFilter.call(this);
    this.categories_ = {};
    var cats = opt_categories || [];
    for (var i = 0; i < cats.length; i++)
      this.addCategory(cats[i]);
  }
  TimelineCategoryFilter.prototype = {
    __proto__: TimelineFilter.prototype,

    addCategory: function(cat) {
      this.categories_[cat] = true;
    },

    matchSlice: function(slice) {
      if (!slice.category)
        return true;
      return !this.categories_[slice.category];
    }
  };

  return {
    filterSliceArray: filterSliceArray,
    TimelineFilter: TimelineFilter,
    TimelineTitleFilter: TimelineTitleFilter,
    TimelineCategoryFilter: TimelineCategoryFilter
  };
});
