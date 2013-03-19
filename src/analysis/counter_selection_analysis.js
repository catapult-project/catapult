// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('ui');
base.require('analysis.single_counter_selection_analysis');

/**
 * @fileoverview Conains class for counter selections
 *
 */

base.exportTo('tracing.analysis', function() {

  /**
   *
   * @constructor
   * @extends {HTMLDivElement}
   */
  var CounterSelectionAnalysis =
      tracing.ui.define('counter-selection-analysis');
  CounterSelectionAnalysis.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.selection_ = undefined;
    },

    set selection(s) {
      if (s.getNumCounterHits() == 0)
        throw new Error('Expected at least 1 counter in selection');
      if (s.getNumSliceHits() != 0)
        throw new Error('Expected only counters in selection');

      this.selection_ = s;
      this.updateContents_();
    },

    get selection() {
      return this.selection_;
    },

    updateContents_: function() {
      this.textContent = '';

      if (!this.selection_.length)
        return;

      var counterHitsSelection =
          this.selection_.getCounterSampleHitsAsSelection();

      var counters = counterHitsSelection;
      var addedHeader = false;
      for (var i = 0; i < counters.length; i++) {
        var counterHit = counters[i];
        var childEl = new tracing.analysis.SingleCounterSelectionAnalysis();
        if (!addedHeader) {
          this.appendChild(childEl.createColumnTitleRow());
          addedHeader = true;
        }
        var childSelection = new tracing.Selection();
        childSelection.pushHit(counterHit);
        childEl.selection = childSelection;
        this.appendChild(childEl);
      }
    }
  };

  return {
    CounterSelectionAnalysis: CounterSelectionAnalysis
  };
});
