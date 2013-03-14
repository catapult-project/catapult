// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('ui');
base.require('analysis.util');

/**
 * @fileoverview Conains classes for slice group selections.
 *
 */

base.exportTo('tracing.analysis', function() {

  /**
   *
   * @constructor
   * @extends {HTMLDivElement}
   */
  var SliceGroupSelectionAnalysis =
      tracing.ui.define('group-slice-selection-analysis');
  SliceGroupSelectionAnalysis.prototype = {
    __proto__: HTMLDivElement.prototype,
    decorate: function() {
      this.selection_ = undefined;
    },

    set selection(s) {
      if (s.getNumSliceHits() == 0)
        throw new Error('Expected at least 1 slice in selection');

      if (s.getNumCounterHits() != 0)
        throw new Error('Expected only slices in selection');

      var firstTitle = s[0].slice.title;
      for (var i = 1; i < s.length; i++) {
        if (s[i].slice.title != firstTitle)
          throw new Error('Expected all slice titles to be equivalent');
      }

      this.selection_ = s;
      this.updateContents_();
    },

    get selection() {
      return this.selection_;
    },

    get roundedSelectionDuration() {
      return this.roundedSelectionDuration_;
    },

    get selectionStartTime() {
      return this.selectionStartTime_;
    },

    get selectionEndTime() {
      return this.selectionEndTime_;
    },

    get occurrences() {
      return this.occurrences_;
    },

    updateContents_: function() {

      var totalDuration = 0;
      var groupStart = undefined;
      var groupEnd = undefined;
      var numOccurrences = this.selection.length;
      for (var i = 0; i < numOccurrences; i++) {
        var slice = this.selection[i].slice;
        totalDuration += slice.duration;
        if (groupStart == undefined || slice.groupStart < groupStart)
          groupStart = slice.start;
        var sliceEnd = slice.end;
        if (groupEnd == undefined || sliceEnd > groupEnd)
          groupEnd = sliceEnd;
      }

      this.roundedSelectionDuration_ = tracing.analysis.tsRound(totalDuration);
      this.selectionStartTime_ = groupStart;
      this.selectionEndTime_ = groupEnd;
      this.occurrences_ = numOccurrences;

      var rowEl = document.createElement('div');
      rowEl.classList.add('analysis-table-row');
      this.createAndAppendSpan_(rowEl, this.selection[0].slice.title);
      this.createAndAppendSpan_(rowEl, this.roundedSelectionDuration_);
      this.createAndAppendSpan_(rowEl, this.occurrences);
      this.appendChild(rowEl);
    },

    createColumnTitleRow: function() {
      this.textContent = '';
      var row = document.createElement('div');
      row.classList.add('analysis-table-row');

      this.createAndAppendSpan_(row, 'Slice Group Title');
      this.createAndAppendSpan_(row, 'Total Duration ms');
      this.createAndAppendSpan_(row, 'Occurrences');

      return row;
    },

    createAndAppendSpan_: function(row, content) {
      var el = document.createElement('span');
      el.textContent = content;
      row.appendChild(el);
    },
  };

  return {
    SliceGroupSelectionAnalysis: SliceGroupSelectionAnalysis
  };

});
