/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {LitElement, html, css} from 'lit-element';
import {afterRender} from './utils.js';

export default class CpTabBar extends LitElement {
  static get is() { return 'cp-tab-bar'; }

  static get properties() {
    return {
      selected: String,
    };
  }

  static get styles() {
    return css`
      :host {
        align-items: center;
        color: var(--primary-color-dark, blue);
        display: flex;
        margin-top: 8px;
      }
    `;
  }

  render() {
    return html`<slot></slot>`;
  }

  updated() {
    for (const item of this.querySelectorAll('cp-tab')) {
      item.checked = (item.name === this.selected);
    }
  }
}

customElements.define(CpTabBar.is, CpTabBar);
