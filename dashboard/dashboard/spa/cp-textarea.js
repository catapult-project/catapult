/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
(() => {
  class CpTextarea extends Polymer.Element {
    static get is() { return 'cp-textarea'; }

    static get template() {
      return Polymer.html`
        <style>
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
        </style>

        <div id="label">[[label]]</div>
        <textarea
            id="input"
            value="[[value]]"
            on-blur="onBlur_"
            on-focus="onFocus_"
            on-keyup="onKeyup_">
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
      return this.$.input;
    }

    async focus() {
      this.nativeInput.focus();
      while (cp.getActiveElement() !== this.nativeInput) {
        await cp.timeout(50);
        this.nativeInput.focus();
      }
    }

    async blur() {
      this.nativeInput.blur();
      while (cp.getActiveElement() === this.nativeInput) {
        await cp.timeout(50);
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

  CpTextarea.properties = {
    autofocus: {type: Boolean},
    focused: {
      type: Boolean,
      reflectToAttribute: true,
    },
    label: {type: String},
    value: {type: String},
  };

  customElements.define(CpTextarea.is, CpTextarea);
})();
