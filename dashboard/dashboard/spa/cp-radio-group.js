/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {PolymerElement, html} from '/@polymer/polymer/polymer-element.js';
import './cp-radio.js';

export default class CpRadioGroup extends PolymerElement {
  static get is() { return 'cp-radio-group'; }

  static get template() {
    return html`
      <style>
        :host {
          display: flex;
          flex-direction: column;
        }
        ::slotted(cp-radio) {
          margin: 4px 0;
        }
      </style>
      <slot></slot>
    `;
  }

  ready() {
    super.ready();
    this.addEventListener('change', this.onItemChange_.bind(this));
  }

  onItemChange_(event) {
    this.selected = event.target.name;
  }

  observeSelected_(newValue, oldValue) {
    for (const item of this.querySelectorAll('cp-radio')) {
      item.checked = (item.name === this.selected);
    }
    this.dispatchEvent(new CustomEvent('selected-changed', {
      bubbles: true,
      composed: true,
      detail: {value: this.selected},
    }));
  }
}

CpRadioGroup.properties = {selected: {type: String}};
CpRadioGroup.observers = ['observeSelected_(selected)'];

customElements.define(CpRadioGroup.is, CpRadioGroup);
