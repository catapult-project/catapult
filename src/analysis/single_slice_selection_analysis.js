// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('ui');
base.require('analysis.util');

/**
 * @fileoverview Conains classes for single slice selection.
 */

base.exportTo('tracing', function() {

  /**
   *
   * @constructor
   * @extends {HTMLDivElement}
   */
  var SingleSliceSelectionAnalysis = base.ui.define('single-slice-selection');
  SingleSliceSelectionAnalysis.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.selection_ = undefined;
      this.hasHeader_ = false;
      this.verticalDisplay_ = false;
    },

    get selection() {
      return this.selection_;
    },

    set selection(selection) {

      if (selection.getNumSliceHits() != 1)
        return;

      this.selection_ = selection;
      this.updateContents_();
    },

    get verticalDisplay() {
      return this.verticalDisplay_;
    },

    set verticalDisplay(b) {
      this.verticalDisplay_ = b;
      updateContents_();
    },

    updateContents_: function() {
      this.textContent = '';

      if (!this.selection_.length)
        return;

      var hit = this.selection_[0];
      var slice = hit.slice;

      this.appendData_('Title', slice.title);
      this.appendData_('Category', slice.category);
      this.appendData_('Start Time', tracing.tsRound(slice.start));
      this.appendData_('Duration', tracing.tsRound(slice.duration));

      this.appendChild(row);
    },

    appendData_: function(title, value) {
      if (this.verticalDisplay) {
        var el = document.createElement('span');
        el.classList.add('analyis-table-row-title');
        el.textContent = title;
        this.appendChild(el);

        el = document.createElement('span');
        el.classList.add('analyis-table-cell');
        el.textContent = value;
        this.appendChild(el);
              return;
      }

      el = document.createElement('span');
      el.classList.add('analyis-table-cell');
      el.textContent = value;
      this.appendChild(el);
    }

  };

  return {
    SingleSliceSelectionAnalysis: SingleSliceSelectionAnalysis
  };
});
