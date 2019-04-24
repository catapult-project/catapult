/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

export default class CpInput extends Polymer.Element {
  static get is() { return 'cp-input'; }

  static get template() {
    return Polymer.html`
      <style>
        :host {
          align-items: center;
          border-radius: 4px;
          border: 1px solid var(--neutral-color-dark, grey);
          cursor: text;
          display: flex;
          justify-content: space-between;
          outline: none;
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
      </style>

      <div id="label">[[label]]</div>
      <input
          id="input"
          size="0"
          disabled="[[disabled]]"
          value="[[value]]"
          on-blur="onBlur_"
          on-focus="onFocus_"
          on-keyup="onKeyup_"></input>
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

  get nativeInput() {
    return this.$.input;
  }

  async onFocus_(event) {
    this.focused = true;
  }

  async onBlur_(event) {
    this.focused = false;
  }

  async focus() {
    this.nativeInput.focus();
    // Sometimes there can be so much rendering happening around
    // connectedCallback and other state updates that the first focus()
    // doesn't take. Try, try again.
    while (cp.getActiveElement() !== this.nativeInput) {
      await cp.timeout(50);
      this.nativeInput.focus();
    }

    // Sometimes calling focus() doesn't dispatch the focus event.
    this.dispatchEvent(new CustomEvent('focus', {
      bubbles: true,
      composed: true,
    }));
  }

  async blur() {
    this.nativeInput.blur();
    while (cp.getActiveElement() === this.nativeInput) {
      await cp.timeout(50);
      this.nativeInput.blur();
    }
  }

  async onKeyup_(event) {
    this.value = event.target.value;
  }
}

CpInput.properties = {
  autofocus: {type: Boolean},
  focused: {
    type: Boolean,
    reflectToAttribute: true,
  },
  disabled: {
    type: Boolean,
    reflectToAttribute: true,
  },
  label: {type: String},
  value: {type: String},
};

customElements.define(CpInput.is, CpInput);
