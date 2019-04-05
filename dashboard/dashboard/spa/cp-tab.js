/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
(() => {
  class CpTab extends Polymer.Element {
    static get is() { return 'cp-tab'; }

    static get template() {
      return Polymer.html`
        <style>
          :host {
            background-color: var(--primary-color-light, lightblue);
            border-left: 1px solid var(--primary-color-dark, blue);
            border-right: 1px solid var(--primary-color-dark, blue);
            cursor: pointer;
            padding: 8px;
          }
          :host([checked]) {
            background-color: var(--primary-color-dark, blue);
            color: var(--background-color, white);
            text-shadow: 1px 0 0 currentColor;
          }
        </style>

        <slot></slot>
      `;
    }
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
