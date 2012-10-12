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

base.exportTo('tracing', function() {

  /**
   *
   * @constructor
   * @extends {HTMLDivElement}
   */
  var SliceSelectionAnalysis = base.ui.define('slice-selection-analysis');
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
        var childEl = new tracing.SingleSliceSelectionAnalysis();
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
        var addedHeader = false;
        for (var groupTitle in selectionsByTitle) {
          var childEl = new tracing.SliceGroupSelectionAnalysis();
          childEl.selection = selectionsByTitle[groupTitle];
          if (!addedHeader) {
            this.appendChild(childEl.createColumnTitleRow());
            addedHeader = true;
          }

          this.appendChild(childEl);
        }

        // TODO (kassycoan): add group summary data.

      }

    },

    /* Helper functions for group slice selectionsByTitle */

    buildSelectionsByTitleByTitle_: function(sliceHits) {
      var selectionsByTitle = {};
      for (var i = 0; i < sliceHits.length; i++) {
        var sliceHit = sliceHits[i];
        var title = sliceHit.slice.title;
        if (!selectionsByTitle[title])
          selectionsByTitle[title] = new tracing.TimelineSelection();
        selectionsByTitle[title].pushHit(sliceHit);
      }
      return selectionsByTitle;
    }

  };

  return {
    SliceSelectionAnalysis: SliceSelectionAnalysis
  };

});
