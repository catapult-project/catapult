// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('analysis.selection_analysis');
base.require('analysis.slice_selection_analysis');
base.require('analysis.counter_selection_analysis');
base.require('ui');

/**
 * @fileoverview Conains classes for general selections.
 *
 */

base.exportTo('tracing.analysis', function() {

  /**
   *
   * @constructor
   * @extends {HTMLDivElement}
   */
  var SelectionAnalysis = tracing.ui.define('selection-analysis');
  SelectionAnalysis.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.selection_ = undefined;
    },

    set selection(s) {
      this.selection_ = s;
      this.updateContents_();
    },

    get selection() {
      return this.selection_;
    },

    updateContents_: function() {
      this.textContent = '';
      var sliceHits = this.selection_.getSliceHitsAsSelection();
      var counterHits = this.selection_.getCounterSampleHitsAsSelection();

      if (sliceHits.length) {
        var childEl = new tracing.analysis.SliceSelectionAnalysis();
        childEl.selection = sliceHits;
        this.appendChild(childEl);
      }
      if (counterHits.length) {
        var childEl = new tracing.analysis.CounterSelectionAnalysis();
        childEl.selection = counterHits;
        this.appendChild(childEl);
      }
    }
  };

  return {
    SelectionAnalysis: SelectionAnalysis
  };

});
