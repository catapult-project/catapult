/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './cp-icon.js';
import '@chopsui/chops-input';
import OptionGroup from './option-group.js';
import {ElementBase, STORE} from './element-base.js';
import {UPDATE} from './simple-redux.js';
import {html, css} from 'lit-element';
import {isElementChildOf} from './utils.js';
import {get, set} from 'dot-prop-immutable';

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
      <chops-input
          id="input"
          ?autofocus="${this.isFocused}"
          .error="${!this.isValid_()}"
          ?disabled="${this.isDisabled_()}"
          .label="${this.label}"
          value="${MenuInput.inputValue(
      this.isFocused, this.query, this.selectedOptions)}"
          @blur="${this.onBlur_}"
          @focus="${this.onFocus_}"
          @keydown="${this.onKeyDown_}"
          @keyup="${this.onKeyUp_}">
        <cp-icon
            id="clear"
            ?hidden="${!this.selectedOptions || !this.selectedOptions.length}"
            icon="cancel"
            title="clear"
            alt="clear"
            @click="${this.onClear_}">
        </cp-icon>
      </chops-input>

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
    this.nativeInput = this.shadowRoot.querySelector('chops-input');
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

  async onKeyDown_(event) {
    if (event.key === 'Escape') {
      this.nativeInput.blur();
      return;
    }

    if (event.key.startsWith('Arrow')) {
      STORE.dispatch({
        type: MenuInput.reducers.arrowCursor.name,
        statePath: this.statePath,
        key: event.key,
      });
      return;
    }

    if (event.key === 'Enter' && this.cursor) {
      STORE.dispatch({
        type: MenuInput.reducers.select.name,
        statePath: this.statePath,
      });
      this.dispatchEvent(new CustomEvent('option-select', {
        bubbles: true,
        composed: true,
      }));
    }
  }

  async onKeyUp_(event) {
    if (event.key.startsWith('Arrow') ||
        event.key === 'Escape' ||
        event.key === 'Enter') {
      // These are handled by onKeyDown_.
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

function optionStatePath(indices) {
  return indices.join('.options.');
}

const ARROW_HANDLERS = {
  // These four methods handle arrow key presses.
  // They may modify `indices` in place. They may NOT modify options in place.
  // They may return options modified via set().
  // `indices` is an array of integer indexes, denoting a path through the
  // option tree. This path is stored in the Redux STORE as a statePath string.
  // MenuInput.reducers.arrowCursor transforms the cursor statePath to `indices`
  // to make it easier for these handlers to modify, then transformed back to a
  // statePath string.
  // `options` is an array of objects that was produced by
  // OptionGroup.groupValues().

  ArrowUp(indices, options, query) {
    if (!indices.length) {
      indices.push(options.length - 1);
      return options;
    }

    const lastIndex = indices[indices.length - 1];
    if (lastIndex === 0) {
      if (indices.length === 1) {
        indices.splice(0, 1, options.length - 1);
      } else {
        indices.pop();
      }
      return options;
    }

    indices[indices.length - 1] -= 1;

    let prevOption = get(options, optionStatePath(indices));
    let isExpanded = prevOption && prevOption.options &&
        prevOption.options.length && (query || prevOption.isExpanded);
    while (isExpanded) {
      indices.push(prevOption.options.length - 1);
      prevOption = prevOption.options[prevOption.options.length - 1];
      isExpanded = prevOption && prevOption.options &&
          prevOption.options.length && (query || prevOption.isExpanded);
    }
    return options;
  },

  ArrowDown(indices, options, query) {
    if (!indices.length) {
      indices.push(0);
      return options;
    }

    const cursorOption = get(options, optionStatePath(indices));
    if (cursorOption && cursorOption.options && cursorOption.options.length &&
        (query || cursorOption.isExpanded)) {
      indices.push(0);
      return options;
    }

    if (indices.length === 1) {
      if (indices[0] === options.length - 1) {
        indices.splice(0, 1, 0);
        return options;
      }
      indices[0] += 1;
      return options;
    }

    let parentPath = optionStatePath(indices.slice(0, indices.length - 1));
    let parentOption = get(options, parentPath);
    while ((indices.length > 1) &&
        (indices[indices.length - 1] === (parentOption.options.length - 1))) {
      indices.pop();
      parentPath = optionStatePath(indices.slice(0, indices.length - 1));
      parentOption = get(options, parentPath);
    }

    indices[indices.length - 1] += 1;
    return options;
  },

  ArrowLeft(indices, options, query) {
    if (!indices.length) return options;

    let cursorRelPath = optionStatePath(indices);
    let cursorOption = get(options, cursorRelPath);
    if (!cursorOption) return options;

    if ((indices.length > 1) && !cursorOption.isExpanded) {
      indices.pop();
      cursorRelPath = optionStatePath(indices);
      cursorOption = get(options, cursorRelPath);
    }

    options = set(options, cursorRelPath + '.isExpanded', false);

    return options;
  },

  ArrowRight(indices, options, query) {
    const cursorRelPath = optionStatePath(indices);
    const cursorOption = get(options, cursorRelPath);
    // If the option at cursor has children, expand it.
    if (cursorOption && cursorOption.options && cursorOption.options.length &&
        !cursorOption.isExpanded) {
      options = set(options, cursorRelPath + '.isExpanded', true);
    }
    return options;
  },
};

MenuInput.reducers = {
  focus: (rootState, {inputStatePath}, rootStateAgain) => {
    const focusTimestamp = window.performance.now();
    rootState = {...rootState, focusTimestamp};
    if (!inputStatePath) return rootState; // Blur all menu-inputs
    return set(rootState, inputStatePath, inputState => {
      return {...inputState, focusTimestamp, hasBeenOpened: true};
    });
  },

  arrowCursor: (state, {key, statePath}, rootState) => {
    if (!ARROW_HANDLERS[key]) return state;

    const indices = [];
    if (state.cursor) {
      const cursorRelPath = state.cursor.substr(
          (statePath + '.options.').length);
      indices.push(...cursorRelPath.split('.options.').map(i => parseInt(i)));
    }

    let options = ARROW_HANDLERS[key](indices, state.options, state.query);

    if (state.query && (key === 'ArrowUp' || key === 'ArrowDown')) {
      const originalIndices = [...indices].join();
      let cursorOption = get(state.options, optionStatePath(indices));
      const queryParts = state.query.toLocaleLowerCase().split(' ');
      while (!OptionGroup.matches(cursorOption, queryParts)) {
        options = ARROW_HANDLERS[key](indices, state.options, state.query);
        cursorOption = get(state.options, optionStatePath(indices));

        if (indices.join() === originalIndices) {
          // No options match the query.
          return {...state, cursor: undefined};
        }
      }
    }

    // Translate indices back to a statePath string.
    indices.unshift(statePath);
    const cursor = optionStatePath(indices);

    return {...state, options, cursor};
  },

  select: (state, {statePath}, rootState) => {
    if (!state.cursor) return state;
    const option = get(rootState, state.cursor);
    if (!option) return state;
    return OptionGroup.reducers.select(state, {option}, rootState);
  },
};

ElementBase.register(MenuInput);
