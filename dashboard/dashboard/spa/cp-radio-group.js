/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {LitElement, html, css} from 'lit-element';
import './cp-radio.js';

export default class CpRadioGroup extends LitElement {
  static get is() { return 'cp-radio-group'; }

  static get properties() {
    return {selected: {type: String}};
  }

  static get styles() {
    return css`
      :host {
        display: flex;
        flex-direction: column;
      }
      ::slotted(cp-radio) {
        margin: 4px 0;
      }
    `;
  }

  constructor() {
    super();
    this.addEventListener('change', this.onItemChange_.bind(this));
  }

  render() {
    return html`<slot></slot>`;
  }

  onItemChange_(event) {
    this.selected = event.target.name;
  }

  updated() {
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

customElements.define(CpRadioGroup.is, CpRadioGroup);
