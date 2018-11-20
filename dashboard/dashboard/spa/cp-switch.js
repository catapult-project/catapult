/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
(() => {
  class CpSwitch extends Polymer.Element {
    static get is() { return 'cp-switch'; }

    click() {
      this.$.native.click();
    }

    onChange_(event) {
      this.dispatchEvent(new CustomEvent('change', {
        bubbles: true,
        composed: true,
      }));
    }
  }

  CpSwitch.properties = {
    checked: {type: Boolean},
    disabled: {type: Boolean},
  };

  customElements.define(CpSwitch.is, CpSwitch);
})();
