/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {LitElement, html, css} from 'lit-element';
import {getActiveElement, timeout} from './utils.js';

export default class CpTextarea extends LitElement {
  static get properties() {
    return {
      autofocus: {type: Boolean},
      focused: {
        type: Boolean,
        reflect: true,
      },
      label: {type: String},
      value: {type: String},
    };
  }

  static get styles() {
    return css`
      :host {
        border-radius: 4px;
        border: 1px solid var(--neutral-color-dark, grey);
        cursor: text;
        display: flex;
        outline: none;
        padding: 4px;
        position: relative;
      }
      #label {
        background-color: var(--background-color, white);
        color: var(--primary-color-dark, blue);
        font-size: smaller;
        padding: 4px;
        position: absolute;
        transform: translate(0px, -1.5em);
        transition: color var(--transition-short, 0.2s);
        white-space: nowrap;
      }
      :host([focused]) {
        border: 2px solid var(--primary-color-dark, blue);
        padding: 3px;
      }
      :host([focused]) #label {
        color: var(--primary-color-dark, blue);
      }
      textarea {
        border: 0;
        flex-grow: 1;
        font-family: inherit;
        font-size: inherit;
        outline: none;
        padding: 4px;
      }
    `;
  }

  render() {
    return html`
      <div id="label">${this.label}</div>
      <textarea
          value="${this.value}"
          @blur="${this.onBlur_}"
          @focus="${this.onFocus_}"
          @keyup="${this.onKeyup_}">
      </textarea>
    `;
  }

  async connectedCallback() {
    super.connectedCallback();
    if (this.autofocus) {
      this.focus();
    }
    this.addEventListener('click', this.onClick_.bind(this));
  }

  async onClick_(event) {
    this.focus();
  }

  get nativeInput() {
    return this.shadowRoot.querySelector('textarea');
  }

  async focus() {
    while (!this.nativeInput) {
      await timeout(50);
    }
    this.nativeInput.focus();
    while (getActiveElement() !== this.nativeInput) {
      await timeout(50);
      this.nativeInput.focus();
    }
  }

  async blur() {
    if (!this.nativeInput) return;
    this.nativeInput.blur();
    while (getActiveElement() === this.nativeInput) {
      await timeout(50);
      this.nativeInput.blur();
    }
  }

  async onFocus_(event) {
    this.focused = true;
  }

  async onBlur_(event) {
    this.focused = false;
  }

  async onKeyup_(event) {
    this.value = event.target.value;
  }
}

customElements.define('cp-textarea', CpTextarea);
