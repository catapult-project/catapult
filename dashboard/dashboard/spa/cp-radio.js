/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {PolymerElement, html} from '/@polymer/polymer/polymer-element.js';

export default class CpRadio extends PolymerElement {
  static get is() { return 'cp-radio'; }

  static get template() {
    return html`
      <style>
        input {
          display: none;
        }
        input:checked + label:before {
          border-color: var(--primary-color-dark, blue);
        }
        input:checked + label:after {
          transform: scale(1);
        }
        label {
          align-items: center;
          display: inline-flex;
          height: 20px;
          position: relative;
          padding: 0 30px;
          margin-bottom: 0;
          cursor: pointer;
          vertical-align: bottom;
          white-space: nowrap;
        }
        label:before, label:after {
          position: absolute;
          content: '';
          border-radius: 50%;
          transition: all var(--transition-short, 0.2s) ease;
          transition-property: transform, border-color;
        }
        label:before {
          box-sizing: border-box;
          left: 0;
          top: 0;
          width: 20px;
          height: 20px;
          border: 2px solid rgba(0, 0, 0, 0.54);
        }
        label:after {
          top: 5px;
          left: 5px;
          width: 10px;
          height: 10px;
          transform: scale(0);
          background: var(--primary-color-dark, blue);
        }
        input:disabled + label:before,
        input:disabled + label:after {
          border-color: var(--neutral-color-dark, darkgrey);
        }
        input:disabled:checked + label:before,
        input:disabled:checked + label:after {
          background: var(--neutral-color-dark, darkgrey);
        }
      </style>

      <input
          type="radio"
          id="native"
          checked="{{checked}}"
          disabled$="[[disabled]]"
          on-change="onChange_">
      <label for="native"><slot></slot></label>
    `;
  }

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
