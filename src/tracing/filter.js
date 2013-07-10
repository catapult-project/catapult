// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

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

  function filterCounterArray(filter, counters) {
    if (filter === undefined)
      return counters;

    var matched = [];
    for (var i = 0; i < counters.length; ++i) {
      if (filter.matchCounter(counters[i]))
        matched.push(counters[i]);
    }
    return matched;
  }

  /**
   * @constructor The generic base class for filtering a TraceModel based on
   * various rules. The base class returns true for everything.
   */
  function Filter() {
  }

  Filter.prototype = {
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
   * @constructor A filter that matches objects by their name case insensitive.
   * .findAllObjectsMatchingFilter
   */
  function TitleFilter(text) {
    Filter.call(this);
    this.text_ = text.toLowerCase();
  }
  TitleFilter.prototype = {
    __proto__: Filter.prototype,

    matchCounter: function(counter) {
      if (this.text_.length === 0)
        return false;
      if (counter.name === undefined)
        return false;
      return counter.name.toLowerCase().indexOf(this.text_) !== -1;
    },

    matchSlice: function(slice) {
      if (this.text_.length === 0)
        return false;
      if (slice.title === undefined)
        return false;
      return slice.title.toLowerCase().indexOf(this.text_) !== -1;
    }
  };

  /**
   * @constructor A filter that filters objects by their category.
   * Objects match if they are NOT in the list of categories
   * @param {Array<string>=} opt_categories Categories to blacklist.
   */
  function CategoryFilter(opt_categories) {
    Filter.call(this);
    this.categories_ = {};
    var cats = opt_categories || [];
    for (var i = 0; i < cats.length; i++)
      this.addCategory(cats[i]);
  }
  CategoryFilter.prototype = {
    __proto__: Filter.prototype,

    addCategory: function(cat) {
      this.categories_[cat] = true;
    },

    matchCounter: function(counter) {
      if (!counter.category)
        return true;
      return !this.categories_[counter.category];
    },

    matchSlice: function(slice) {
      if (!slice.category)
        return true;
      return !this.categories_[slice.category];
    }
  };

  return {
    filterCounterArray: filterCounterArray,
    filterSliceArray: filterSliceArray,
    Filter: Filter,
    TitleFilter: TitleFilter,
    CategoryFilter: CategoryFilter
  };
});
