/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
(() => {
  class CpRadio extends Polymer.Element {
    static get is() { return 'cp-radio'; }

    onChange_(event) {
      this.dispatchEvent(new CustomEvent('change', {
        bubbles: true,
        composed: true,
      }));
    }
  }

  CpRadio.properties = {
    name: {type: String},
    checked: {type: Boolean},
    disabled: {type: Boolean},
  };

  customElements.define(CpRadio.is, CpRadio);
})();
