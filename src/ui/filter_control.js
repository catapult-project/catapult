// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Filter Control.
 */
base.requireStylesheet('ui.filter_control');
base.require('tracing.filter');
base.require('ui');
base.require('ui.overlay');
base.exportTo('ui', function() {

  /**
   * FilterControl
   * @constructor
   */
  var FilterControl = ui.define('span');

  FilterControl.prototype = {
    __proto__: HTMLSpanElement.prototype,

    decorate: function() {
      this.className = 'filter-control';
      // Filter input element.
      this.filterEl_ = document.createElement('input');
      this.filterEl_.type = 'input';

      this.hitCountEl_ = document.createElement('span');
      this.hitCountEl_.className = 'hit-count-label';

      this.filterEl_.addEventListener('input', function(e) {
        this.filterText = this.filterEl_.value;
      }.bind(this));

      this.filterEl_.addEventListener('keydown', function(e) {
        if (e.keyCode == 27) { // Escape
          this.filterEl_.blur();
        }
      }.bind(this));

      this.addEventListener(
          'hitCountTextChange',
          this.updateHitCountEl_.bind(this)
      );

      this.addEventListener(
          'filterTextChange',
          this.onFilterTextChange_.bind(this)
      );

      // Attach everything.
      this.appendChild(this.filterEl_);
      this.appendChild(this.hitCountEl_);

      this.filterText = '';
      this.hitCountText = '0 of 0';
    },

    focus: function() {
      this.filterEl_.selectionStart = 0;
      this.filterEl_.selectionEnd = this.filterEl_.value.length;
      this.filterEl_.focus();
    },

    updateHitCountEl_: function(event) {
      this.hitCountEl_.textContent = event ? event.newValue : '';
    },

    onFilterTextChange_: function() {
      this.filterEl_.value = event.newValue;
    }
  };

  // Outgoing change events
  base.defineProperty(FilterControl, 'filterText',
      base.PropertyKind.JS, null, true);

  // Incoming change events
  base.defineProperty(FilterControl, 'hitCountText',
      base.PropertyKind.JS, null, true);

  return {
    FilterControl: FilterControl
  };
});

