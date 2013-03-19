// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('analysis.single_slice_selection_analysis');
base.require('analysis.slice_group_selection_analysis');

/**
 * @fileoverview Conains classes for slice selectionsByTitle.
 *
 */

base.exportTo('tracing.analysis', function() {

  /**
   *
   * @constructor
   * @extends {HTMLDivElement}
   */
  var SliceSelectionAnalysis = tracing.ui.define('slice-selection-analysis');
  SliceSelectionAnalysis.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.selection_ = undefined;
    },

    set selection(s) {
      if (s.getNumSliceHits() == 0)
        throw new Error('Expected at least 1 slice in selection');

      if (s.getNumCounterHits() != 0)
        throw new Error('Expected only slices in selection');

      this.selection_ = s;
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

      var sliceHitsSelection = this.selection_.getSliceHitsAsSelection();

      if (sliceHitsSelection.length == 1) {
        var childEl = new tracing.analysis.SingleSliceSelectionAnalysis();
        childEl.verticalDisplay_ = true;
        childEl.selection = sliceHitsSelection;
        this.appendChild(childEl);
      } else if (sliceHitsSelection.length > 1) {
        var selectionsByTitle = this.buildSelectionsByTitleByTitle_(
            this.selection_);
        /*
         * Create selectionsByTitle of slice hits organized by title
         * and for each selection of hits, create a group analysis
         * and append accordingly.
         */

        // Initialize varibales for summary of groups.
        var allGroupsDuration = 0;
        var allGroupsOccurrences = 0;
        var allGroupsEnd = undefined;
        var allGroupsStart = undefined;

        var addedHeader = false;
        for (var groupTitle in selectionsByTitle) {
          var childEl = new tracing.analysis.SliceGroupSelectionAnalysis();
          if (!addedHeader) {
            this.appendChild(childEl.createColumnTitleRow());
            addedHeader = true;
          }
          childEl.selection = selectionsByTitle[groupTitle];

          this.appendChild(childEl);

          allGroupsDuration += childEl.roundedSelectionDuration;
          allGroupsOccurrences += childEl.occurrences;
          if (allGroupsEnd == undefined ||
              childEl.selectionEndTime > allGroupsEnd) {
            allGroupsEnd = childEl.selectionEndTime;
          }
          if (allGroupsStart == undefined ||
              childEl.selectionStartTime < allGroupsStart) {
            allGroupsStart = childEl.selectionStartTime;
          }
        }

        // Construct and append the groups summary.
        var groupSummaryEl = document.createElement('group-totals-summary');
        this.appendDataRow_(groupSummaryEl, 'Totals',
            tracing.analysis.tsRound(allGroupsDuration), allGroupsOccurrences);
        this.appendDataRow_(groupSummaryEl, 'Selection Start',
            tracing.analysis.tsRound(allGroupsStart));
        this.appendDataRow_(groupSummaryEl, 'Selection End',
            tracing.analysis.tsRound(allGroupsEnd));
        this.appendChild(groupSummaryEl);
      }
    },

    buildSelectionsByTitleByTitle_: function(sliceHits) {
      var selectionsByTitle = {};
      for (var i = 0; i < sliceHits.length; i++) {
        var sliceHit = sliceHits[i];
        var title = sliceHit.slice.title;
        if (!selectionsByTitle[title])
          selectionsByTitle[title] = new tracing.Selection();
        selectionsByTitle[title].pushHit(sliceHit);
      }
      return selectionsByTitle;
    },

    appendDataRow_: function(parentContainer, title, value,
        additional_valueCell) {
      var rowEl = document.createElement('div');
      rowEl.classList.add('analysis-table-row');

      var el = document.createElement('span');
      el.classList.add('analysis-table-row-title');
      el.textContent = title;
      rowEl.appendChild(el);

      el = document.createElement('span');
      el.classList.add('analysis-table-cell');
      el.textContent = value;
      rowEl.appendChild(el);

      if (additional_valueCell) {
        el = document.createElement('span');
        el.classList.add('analyis-table-cell');
        el.textContent = additional_valueCell;
        rowEl.appendChild(el);
      }
      parentContainer.appendChild(rowEl);
    }

  };

  return {
    SliceSelectionAnalysis: SliceSelectionAnalysis
  };

});
