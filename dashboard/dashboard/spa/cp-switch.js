/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {PolymerElement, html} from '/@polymer/polymer/polymer-element.js';

export default class CpSwitch extends PolymerElement {
  static get is() { return 'cp-switch'; }

  static get template() {
    return html`
      <style>
        :host {
          padding: 8px;
        }
        input {
          display: none;
        }
        label {
          position: relative;
          cursor: pointer;
          padding: 8px 0 8px 44px;
        }
        label:before, label:after {
          content: "";
          position: absolute;
          margin: 0;
          outline: 0;
          top: 50%;
          transform: translate(0, -50%);
          transition: all var(--transition-short, 0.2s) ease;
        }
        label:before {
          left: 1px;
          width: 34px;
          height: 14px;
          background-color: var(--neutral-color-dark, grey);
          border-radius: 8px;
        }
        label:after {
          background-color: var(--neutral-color-light, lightgrey);
          border-radius: 50%;
          box-shadow: var(--elevation-2);
          height: 20px;
          left: 0;
          width: 20px;
        }
        input:checked + label:before {
          background-color: var(--primary-color-medium, lightblue);
        }
        input:checked + label:after {
          background-color: var(--primary-color-dark, blue);
          transform: translate(80%, -50%);
        }
      </style>

      <input
          type="checkbox"
          id="native"
          checked="{{checked}}"
          disabled$="[[disabled]]"
          on-change="onChange_">
      <label for="native"><slot></slot></label>
    `;
  }

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
