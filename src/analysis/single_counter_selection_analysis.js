// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('ui');
base.require('analysis.util');

/**
 * @fileoverview Conains classes for single counter selections.
 */

base.exportTo('tracing.analysis', function() {

  /**
   *
   * @constructor
   * @extends {HTMLDivElement}
   */
  var SingleCounterSelectionAnalysis =
      tracing.ui.define('single-counter-selection');

  SingleCounterSelectionAnalysis.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.selection_ = undefined;
    },

    set selection(selection) {

      if (selection.getNumSliceHits() != 0)
        throw new Error('Expected only counters in selection');

      if (selection.getNumCounterHits() != 1)
        throw new Error('Expected only 1 counter in selection');

      this.selection_ = selection;
      this.updateContents_();
    },

    get selection() {
      return this.selection_;
    },

    set verticalDisplay(bool) {
      this.verticalDisplay_ = bool;
    },

    get verticalDisplay() {
      return this.verticalDisplay_;
    },

    updateContents_: function() {
      this.textContent = '';

      if (!this.selection_.length)
        return;

      var hit = this.selection_[0];
      var counter = hit.counter;
      var sampleIndex = hit.sampleIndex;

      var rowEl = document.createElement('div');
      rowEl.classList.add('analysis-table-row');
      this.createAndAppendSpan_(rowEl, counter.name);
      this.createAndAppendSpan_(rowEl, sampleIndex);
      this.appendChild(rowEl);
    },

    createColumnTitleRow: function() {
      this.textContent = '';
      var row = document.createElement('div');

      this.createAndAppendSpan_(row, 'Counter Title');
      this.createAndAppendSpan_(row, 'Timestamp');

      return row;
    },

    createAndAppendSpan_: function(row, content) {
      var el = document.createElement('span');
      el.classList.add('analyis-table-cell');
      el.textContent = content;
      row.appendChild(el);
    },

  };

  return {
      SingleCounterSelectionAnalysis: SingleCounterSelectionAnalysis
  };
});
