// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview A text widget for monitoring ValueBar value and previewValue.
 */
base.require('ui');
base.require('base.properties');
base.require('ui.mouse_tracker');

base.exportTo('ui', function() {

  /**
   * @constructor
   */
  var ValueDisplay = ui.define('value-display');

  ValueDisplay.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.className = 'value-display';
      this.currentValueDisplay_ = ui.createDiv({
        className: 'value-value',
        parent: this
      });
      this.previewValueDisplay_ = ui.createDiv({
        className: 'value-set-to',
        parent: this
      });
      this.setValueText_ = this.setValueText_.bind(this);
      this.setPreviewValueText_ = this.setPreviewValueText_.bind(this);
    },

    get valueBar() {
      return this.valueBar_;
    },

    set valueBar(newValue) {
      if (this.valueBar_)
        this.detach_();
      this.valueBar_ = newValue;
      if (this.valueBar_)
        this.attach_();
    },

    attach_: function() {
      this.valueBar_.addEventListener('valueChange',
          this.setValueText_);
      this.valueBar_.addEventListener('previewValueChange',
          this.setPreviewValueText_);
    },

    dettach_: function() {
      this.valueBar_.removeEventListener('valueChange',
          this.setValueText_);
      this.valueBar_.removeEventListener('previewValueChange',
          this.setPreviewValueText_);
    },

    setValueText_: function(event) {
      if (typeof event.newValue === undefined)
        return;
      this.currentValueDisplay_.textContent = event.newValue.toFixed(2);
      this.setPreviewValueText_(event);
    },

    setPreviewValueText_: function(event) {
      this.previewValueDisplay_.textContent =
          ' (\u2192 ' + event.newValue.toFixed(2) + ')';
    }

  };

  return {
    ValueDisplay: ValueDisplay
  };
});
