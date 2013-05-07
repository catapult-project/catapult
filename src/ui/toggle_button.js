// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.


/**
 * @fileoverview ToggleButton: click toggles isTrue.
 */
base.require('ui');
base.exportTo('ui', function() {

  /**
   * @constructor
   */
  var ToggleButton = ui.define('span');

  ToggleButton.plus = '\u002b';
  ToggleButton.minus = '\u002D';
  ToggleButton.x = '\u00D7';
  ToggleButton.checkMark = '\u221A';
  ToggleButton.blank = '&nbsp;';

  ToggleButton.prototype = {
    __proto__: HTMLSpanElement.prototype,

    isTrueText: ToggleButton.x,
    isFalseText: ToggleButton.blank,

    toggle_: function() {
      this.isTrue = !this.isTrue;
      this.textSpan_.textContent =
        this.isTrue ? this.isTrueText : this.isFalseText;
    },

    decorate: function() {
      this.classList.add('toggle-button');
      this.textSpan_ = document.createElement('span');
      this.textSpan_.className = 'toggle-button-text';
      this.appendChild(this.textSpan_);

      this.isTrue = false;
      this.toggle_();
      this.addEventListener('click', this.toggle_.bind(this));
    }
  };

  base.defineProperty(ToggleButton, 'isTrue', base.PropertyKind.BOOL_ATTR);

  return {
    ToggleButton: ToggleButton
  };

});
