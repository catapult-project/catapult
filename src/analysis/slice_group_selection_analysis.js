// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Conains classes for slice group selections.
 *
 */

base.exportTo('tracing', function() {

  /**
   *
   * @constructor
   * @extends {HTMLDivElement}
   */
  var SliceGroupSelectionAnalysis =
                              base.ui.define('group-slice-selection-analysis');
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

    updateContents_: function() {
      this.textContent = '';

      var totalDuration = 0;
      var occurrences = this.selection[i].length;
      for (var i = 0; i < occurrences; i++) {
        var slice = this.selection[i].slice;
        totalDuration += slice.duration;
      }

      var roundedTotalDuration = tracing.tsRound(totalDuration);

      this.createAndAppendSpan_(this, this.selection[0].slice.title);
      this.createAndAppendSpan_(this, roundedTotalDuration);
      this.createAndAppendSpan_(this, occurrences);
    },

    createColumnTitleRow: function() {
      this.textContent = '';
      var row = document.createElement('div');

      this.createAndAppendSpan_(row, 'Slice Group Title');
      this.createAndAppendSpan_(row, 'Total Duration ms');
      this.createAndAppendSpan_(row, 'Occurrences');

      this.appendChild(row);
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
