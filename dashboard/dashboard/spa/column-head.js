/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './cp-icon.js';
import {LitElement, html, css} from 'lit-element';

export class ColumnHead extends LitElement {
  static get is() { return 'column-head'; }

  static get properties() {
    return {
      disabled: {
        type: Boolean,
        reflect: true,
        value: false,
      },
      name: {
        type: String,
        value: '',
      },
      sortColumn: {
        type: String,
        value: '',
      },
      sortDescending: {
        type: Boolean,
        value: false,
      },
    };
  }

  static get styles() {
    return css`
      :host {
        align-items: center;
        background-position: center;
        display: flex;
        justify-content: center;
        transition: background var(--transition-long, 1s);
      }
      :host(:not([disabled])) {
        cursor: pointer;
      }
      :host(:hover:not([disabled])) {
        background: white radial-gradient(circle, transparent 1%, white 1%)
        center/15000%;
      }
      :host(:active:not([disabled])) {
        background-color: var(--primary-color-medium, lightblue);
        background-size: 100%;
        transition: background 0s;
      }
      #icon {
        transition: color var(--transition-short, 0.5s);
      }
      #icon[empty] {
        color: transparent;
      }
    `;
  }

  render() {
    const icon = this.sortDescending ? 'down' : 'up';
    return html`
      <cp-icon
          id="icon"
          ?empty="${this.disabled || (this.name !== this.sortColumn)}"
          .icon="${icon}">
      </cp-icon>
      <slot></slot>
    `;
  }

  firstUpdated() {
    this.icon = this.shadowRoot.querySelector('#icon');
  }
}

customElements.define(ColumnHead.is, ColumnHead);
