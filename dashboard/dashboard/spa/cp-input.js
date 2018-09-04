/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
(() => {
  class CpInput extends Polymer.Element {
    static get is() { return 'cp-input'; }

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
})();
