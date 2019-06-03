/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './cp-icon.js';
import './cp-input.js';
import OptionGroup from './option-group.js';
import {ElementBase, STORE} from './element-base.js';
import {UPDATE} from './simple-redux.js';
import {html, css} from 'lit-element';
import {isElementChildOf, get, setImmutable} from './utils.js';

export default class MenuInput extends ElementBase {
  static get is() { return 'menu-input'; }

  static get properties() {
    return {
      statePath: String,
      ...OptionGroup.properties,
      label: String,
      focusTimestamp: Number,
      largeDom: Boolean,
      hasBeenOpened: Boolean,
      isFocused: Boolean,
      required: Boolean,
      requireSingle: Boolean,
    };
  }

  static buildState(options = {}) {
    return {
      ...OptionGroup.buildState(options),
      alwaysEnabled: options.alwaysEnabled !== false,
      hasBeenOpened: false,
      label: options.label || '',
      requireSingle: options.requireSingle || false,
      required: options.required || false,
    };
  }

  static get styles() {
    return css`
      :host {
        display: block;
        padding-top: 12px;
      }

      #clear {
        color: var(--neutral-color-dark, grey);
        cursor: pointer;
        flex-shrink: 0;
      }

      #menu {
        background-color: var(--background-color, white);
        box-shadow: var(--elevation-2);
        max-height: 600px;
        outline: none;
        overflow: auto;
        padding-right: 8px;
        position: absolute;
        z-index: var(--layer-menu, 100);
      }

      #bottom {
        display: flex;
      }
    `;
  }

  render() {
    return html`
      <cp-input
          id="input"
          ?autofocus="${this.isFocused}"
          .error="${!this.isValid_()}"
          ?disabled="${this.isDisabled_()}"
          .label="${this.label}"
          value="${MenuInput.inputValue(
      this.isFocused, this.query, this.selectedOptions)}"
          @blur="${this.onBlur_}"
          @focus="${this.onFocus_}"
          @keyup="${this.onKeyup_}">
        <cp-icon
            id="clear"
            ?hidden="${!this.selectedOptions || !this.selectedOptions.length}"
            icon="cancel"
            title="clear"
            alt="clear"
            @click="${this.onClear_}">
        </cp-icon>
      </cp-input>

      <div id="menu" tabindex="0" ?hidden="${!this.isFocused}">
        <slot name="top"></slot>
        <div id="bottom">
          <slot name="left"></slot>
          <option-group
              .statePath="${this.statePath}"
              .rootStatePath="${this.statePath}">
          </option-group>
        </div>
      </div>
    `;
  }

  stateChanged(rootState) {
    if (!this.statePath) return;
    this.largeDom = rootState.largeDom;
    this.rootFocusTimestamp = rootState.focusTimestamp;
    Object.assign(this, get(rootState, this.statePath));

    const isFocused = (this.focusTimestamp || false) &&
      (rootState.focusTimestamp === this.focusTimestamp);
    const focusChanged = (isFocused !== this.isFocused);
    this.isFocused = isFocused;
    if (focusChanged) this.observeIsFocused_();
  }

  firstUpdated() {
    this.nativeInput = this.shadowRoot.querySelector('cp-input');
    this.observeIsFocused_();
  }

  async observeIsFocused_() {
    if (!this.nativeInput) return;
    if (this.isFocused) {
      this.nativeInput.focus();
    } else {
      this.nativeInput.blur();
    }
  }

  isDisabled_() {
    return !this.alwaysEnabled && this.options && (this.options.length === 0);
  }

  isValid_() {
    if (this.isDisabled_(this.alwaysEnabled, this.options)) return true;
    if (!this.required) return true;
    if (!this.requireSingle && this.selectedOptions.length) {
      return true;
    }
    if (this.requireSingle && (this.selectedOptions.length === 1)) return true;
    return false;
  }

  async onFocus_(event) {
    if (this.isFocused) return;
    MenuInput.focus(this.statePath);
  }

  async onBlur_(event) {
    if (isElementChildOf(event.relatedTarget, this)) {
      this.nativeInput.focus();
      return;
    }
    STORE.dispatch(UPDATE(this.statePath, {
      focusTimestamp: window.performance.now(),
      query: '',
    }));
  }

  async onKeyup_(event) {
    if (event.key === 'Escape') {
      this.nativeInput.blur();
      return;
    }
    STORE.dispatch(UPDATE(this.statePath, {query: event.target.value}));
    this.dispatchEvent(new CustomEvent('input-keyup', {
      detail: {
        key: event.key,
        value: this.query,
      },
    }));
  }

  async onClear_(event) {
    STORE.dispatch(UPDATE(this.statePath, {query: '', selectedOptions: []}));
    MenuInput.focus(this.statePath);
    this.dispatchEvent(new CustomEvent('clear'));
    this.dispatchEvent(new CustomEvent('option-select', {
      bubbles: true,
      composed: true,
    }));
  }

  static focus(inputStatePath) {
    STORE.dispatch({
      type: MenuInput.reducers.focus.name,
      // NOT "statePath"! statePathReducer would mess that up.
      inputStatePath,
    });
  }

  static blurAll() {
    STORE.dispatch({type: MenuInput.reducers.focus.name});
  }
}

MenuInput.inputValue = (isFocused, query, selectedOptions) => {
  if (isFocused) return query;
  if (selectedOptions === undefined) return '';
  if (selectedOptions.length === 0) return '';
  if (selectedOptions.length === 1) return selectedOptions[0];
  return `[${selectedOptions.length} selected]`;
};

MenuInput.reducers = {
  focus: (rootState, {inputStatePath}, rootStateAgain) => {
    const focusTimestamp = window.performance.now();
    rootState = {...rootState, focusTimestamp};
    if (!inputStatePath) return rootState; // Blur all menu-inputs
    return setImmutable(rootState, inputStatePath, inputState => {
      return {...inputState, focusTimestamp, hasBeenOpened: true};
    });
  },
};

ElementBase.register(MenuInput);
