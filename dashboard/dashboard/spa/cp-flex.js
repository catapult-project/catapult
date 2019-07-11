/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {LitElement, html, css} from 'lit-element';

class CpFlex extends LitElement {
  static get is() { return 'cp-flex'; }

  static get styles() {
    return css`
      :host {
        display: flex;
      }
      :host([hidden]) {
        display: none;
      }
      :host([column]) {
        flex-direction: column;
      }
      :host([grows]) ::slotted(*) {
        flex-grow: 1;
      }
    `;
  }

  render() {
    return html`<slot></slot>`;
  }
}

customElements.define(CpFlex.is, CpFlex);
