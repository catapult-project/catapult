// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview A scrollbar-like control with constant text hi/lo values.
 */
base.require('ui');
base.require('base.properties');
base.require('ui.value_bar');

base.exportTo('ui', function() {

  /**
   * @constructor
   */
  var TextEndValueBar = ui.define('text-end-value-bar');

  TextEndValueBar.prototype = {
    __proto__: ui.ValueBar.prototype,

    decorate: function() {
      this.lowestValueProperties_ = {textContent: ''};
      this.highestValueProperties_ = {textContent: ''};
      ui.ValueBar.prototype.decorate.call(this);
      this.classList.add('text-end-value-bar');
    },

    get lowestValueProperties() {
      return this.lowestValueProperties_;
    },

    set lowestValueProperties(newValue) {
      console.assert(typeof newValue === 'object' &&
          (newValue.style || newValue.textContent));
      this.lowestValueProperties_ = newValue;
      base.dispatchPropertyChange(this, 'lowestValue',
          this.lowestValue, this.lowestValue);
    },

    get highestValueProperties() {
      return this.highestValueProperties_;
    },

    set highestValueProperties(newValue) {
      console.assert(typeof newValue === 'object' &&
          (newValue.style || newValue.textContent));
      this.highestValueProperties_ = newValue;
      base.dispatchPropertyChange(this, 'highestValue',
          this.highestValue, this.highestValue);
    },

    copyOwnProperties_: function(dst, src) {
      if (!src)
        return;
      Object.keys(src).forEach(function(key) {
        dst[key] = src[key];
      });
    },

    updateLowestValueElement: function(element) {
      this.copyOwnProperties_(element.style,
          this.lowestValueProperties_.style);
      element.textContent = this.lowestValueProperties_.textContent || '';
    },

    updateHighestValueElement: function(element) {
      this.copyOwnProperties_(element.style,
          this.highestValueProperties_.style);
      element.textContent = this.highestValueProperties_.textContent || '';
    },

  };

  return {
    TextEndValueBar: TextEndValueBar
  };
});
