/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {LitElement, html, css} from 'lit-element';
import {afterRender, getActiveElement, timeout} from './utils.js';

export default class CpInput extends LitElement {
  static get properties() {
    return {
      autofocus: {type: Boolean},
      focused: {
        type: Boolean,
        reflect: true,
      },
      disabled: {
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
        align-items: center;
        border-radius: 4px;
        border: 1px solid var(--neutral-color-dark, grey);
        cursor: text;
        display: flex;
        justify-content: space-between;
        padding: 4px;
        position: relative;
      }
      #label {
        background-color: var(--background-color, white);
        color: var(--neutral-color-dark, grey);
        font-size: smaller;
        padding: 4px;
        position: absolute;
        transform: translate(0px, -1.5em);
        transition: color var(--transition-short, 0.2s);
        white-space: nowrap;
      }
      :host([disabled]) {
        border: 1px solid var(--neutral-color-light, lightgrey);
        cursor: unset;
      }
      :host([focused]) {
        border: 2px solid var(--primary-color-dark, blue);
        padding: 3px;
      }
      :host([focused]) #label {
        color: var(--primary-color-dark, blue);
      }
      :host([error]) {
        border-color: var(--error-color, red);
      }
      input {
        background-color: inherit;
        border: 0;
        box-sizing: border-box;
        flex-grow: 1;
        font-size: inherit;
        outline: none;
        padding: 8px 4px 4px 4px;
        width: 100%;
      }
    `;
  }

  render() {
    return html`
      <div id="label">${this.label}</div>
      <input
          id="input"
          size="0"
          ?disabled="${this.disabled}"
          .value="${this.value}"
          @blur="${this.onBlur_}"
          @focus="${this.onFocus_}"
          @keyup="${this.onKeyup_}"></input>
      <slot></slot>
    `;
  }

  connectedCallback() {
    super.connectedCallback();
    if (this.autofocus) {
      this.focus();
    }
    this.addEventListener('click', this.onClick_.bind(this));
  }

  async onClick_(event) {
    this.focus();
  }

  firstUpdated() {
    this.nativeInput = this.shadowRoot.querySelector('#input');
  }

  async onFocus_(event) {
    this.focused = true;
  }

  async onBlur_(event) {
    this.focused = false;
  }

  async focus() {
    while (!this.nativeInput) {
      await afterRender();
    }
    this.nativeInput.focus();
    // Sometimes there can be so much rendering happening around
    // connectedCallback and other state updates that the first focus()
    // doesn't take. Try, try again.
    while (getActiveElement() !== this.nativeInput) {
      await timeout(50);
      this.nativeInput.focus();
    }

    // Sometimes calling focus() doesn't dispatch the focus event.
    this.dispatchEvent(new CustomEvent('focus', {
      bubbles: true,
      composed: true,
    }));
  }

  async blur() {
    if (!this.nativeInput) return;
    this.nativeInput.blur();
    while (getActiveElement() === this.nativeInput) {
      await timeout(50);
      this.nativeInput.blur();
    }
  }

  async onKeyup_(event) {
    this.value = event.target.value;
  }
}

customElements.define('cp-input', CpInput);
