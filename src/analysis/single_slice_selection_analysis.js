// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('ui');
base.require('analysis.util');

/**
 * @fileoverview Conains classes for single slice selection.
 */

base.exportTo('tracing.analysis', function() {

  /**
   *
   * @constructor
   * @extends {HTMLDivElement}
   */
  var SingleSliceSelectionAnalysis =
      tracing.ui.define('single-slice-selection');
  SingleSliceSelectionAnalysis.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.selection_ = undefined;
      this.verticalDisplay_ = false;
    },

    get selection() {
      return this.selection_;
    },

    set selection(selection) {

      if (selection.getNumCounterHits() != 0)
        throw new Error('Expected only slices in selection');

      if (selection.getNumSliceHits() != 1)
        throw new Error('Expected only 1 slice in selection');

      this.selection_ = selection;
      this.updateContents_();
    },

    get verticalDisplay() {
      return this.verticalDisplay_;
    },

    set verticalDisplay(b) {
      this.verticalDisplay_ = b;
      this.updateContents_();
    },

    updateContents_: function() {
      this.textContent = '';

      if (!this.selection_.length)
        return;

      var hit = this.selection_[0];
      var slice = hit.slice;

      if (this.verticalDisplay) {
        this.appendDataRow_('Title', slice.title);
        this.appendDataRow_('Category', slice.category);
        this.appendDataRow_('Start Time',
                            tracing.analysis.tsRound(slice.start));
        this.appendDataRow_('Duration',
                            tracing.analysis.tsRound(slice.duration));
      }else {
        var rowEl = document.createElement('div');
        rowEl.classList.add('analysis-table-row');
        this.appendData_(rowEl, slice.category);
        this.appendData_(rowEl, tracing.analysis.tsRound(slice.start));
        this.appendData_(rowEl, tracing.analysis.tsRound(slice.duration));
        this.appendChild(rowEl);
      }

      var n = 0;
      for (var name in slice.args) {
        n += 1;
      }

      if (n > 0) {
        var el = document.createElement('div');
        el.classList.add('analysis-table-row');
        this.appendData_(el, 'Args');
        this.appendChild(el);

        for (var name in slice.args) {
          this.appendDataRow_(name, slice.args[name]);
        }
      }

    },

    appendDataRow_: function(title, value) {
      var rowEl = document.createElement('div');
      rowEl.classList.add('analysis-table-row');

      var el = document.createElement('span');
      el.classList.add('analysis-table-row-title');
      el.textContent = title;
      rowEl.appendChild(el);

      el = document.createElement('span');
      el.classList.add('analysis-table-cell');
      if (value == false && value != 0)
        value = '-';
      el.textContent = value;
      rowEl.appendChild(el);

      this.appendChild(rowEl);
    },

    appendData_: function(rowEl, value) {
      var el = document.createElement('span');
      el.classList.add('analysis-table-cell');
      if (value == false)
        value = '-';
      el.textContent = value;
      rowEl.appendChild(el);
    },

    createColumnTitleRow: function() {
      if (this.verticalDisplay)
        throw new error('Cannot mix vertical and horizontal displays.');

      this.textContent = '';
      var row = document.createElement('div');
      row.classList.add('analysis-table-row');
      row.classList.add('column-title-row');

      this.createAndAppendSpan_(row, 'Slice Category');
      this.createAndAppendSpan_(row, 'Start Time');
      this.createAndAppendSpan_(row, 'Duration ms');

      return row;
    },

    createAndAppendSpan_: function(row, content) {
      var el = document.createElement('span');
      el.textContent = content;
      row.appendChild(el);
    },

  };

  return {
    SingleSliceSelectionAnalysis: SingleSliceSelectionAnalysis
  };
});
