// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.


/**
 * @fileoverview ToggleButton: click toggles isOn.
 */
base.require('ui');
base.exportTo('ui', function() {

  /**
   * @constructor
   */
  var ToggleButton = ui.define('span');

  ToggleButton.plus = '\u002b';
  ToggleButton.minus = '\u2012';
  ToggleButton.x = '\u00D7';
  ToggleButton.checkMark = '\u221A';
  ToggleButton.blank = '\u00A0';
  ToggleButton.bullet = '\u2022';

  ToggleButton.prototype = {
    __proto__: HTMLSpanElement.prototype,

    isOnText: ToggleButton.x,
    notIsOnText: ToggleButton.blank,

    toggle_: function() {
      this.isOn = !this.isOn;
    },

    decorate: function() {
      this.classList.add('toggle-button');

      this.borderSpan_ = document.createElement('span');
      this.borderSpan_.className = 'toggle-button-border';

      this.textSpan_ = document.createElement('span');
      this.textSpan_.className = 'toggle-button-text';

      this.appendChild(this.borderSpan_);
      this.appendChild(this.textSpan_);

      this.isOn = true;
      this.textSpan_.textContent = this.isOnText;

      this.addEventListener('click', this.toggle_.bind(this));
      this.addEventListener('isOnChange', function(event) {
        this.textSpan_.textContent =
            this.isOn ? this.isOnText : this.notIsOnText;
      }.bind(this));

    }
  };

  base.defineProperty(ToggleButton, 'isOn',
      base.PropertyKind.BOOL_ATTR, null, true);

  return {
    ToggleButton: ToggleButton
  };

});
