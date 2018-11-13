/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
(() => {
  class CpCheckbox extends Polymer.Element {
    static get is() { return 'cp-checkbox'; }

    click() {
      this.$.native.click();
    }

    onChange_(event) {
      this.dispatchEvent(new CustomEvent('change', {
        bubbles: true,
        composed: true,
        detail: {event},
      }));
    }
  }

  CpCheckbox.properties = {
    checked: {type: Boolean},
    disabled: {type: Boolean},
  };

  customElements.define(CpCheckbox.is, CpCheckbox);
})();
