/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
(() => {
  class CpTab extends Polymer.Element {
    static get is() { return 'cp-tab'; }
  }

  CpTab.properties = {
    checked: {
      type: Boolean,
      reflectToAttribute: true,
    },
    disabled: {type: Boolean},
    name: {type: String},
  };

  customElements.define(CpTab.is, CpTab);
})();
