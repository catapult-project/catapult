/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class MenuInput extends cp.ElementBase {
    connectedCallback() {
      super.connectedCallback();
      this.observeIsFocused_();
    }

    async observeIsFocused_() {
      if (this.isFocused) {
        this.$.input.focus();
      } else {
        this.$.input.blur();
      }
    }

    isDisabled_(alwaysEnabled, options) {
      return !alwaysEnabled && options && (options.length === 0);
    }

    isValid_(selectedOptions, alwaysEnabled, options) {
      if (this.isDisabled_(alwaysEnabled, options)) return true;
      if (!this.required) return true;
      if (!this.requireSingle && !this.isEmpty_(selectedOptions)) return true;
      if (this.requireSingle && (selectedOptions.length === 1)) return true;
      return false;
    }

    getInputValue_(isFocused, query, selectedOptions) {
      return MenuInput.inputValue(isFocused, query, selectedOptions);
    }

    async onFocus_(event) {
      await this.dispatch('focus', this.statePath);
    }

    async onBlur_(event) {
      if (cp.isElementChildOf(event.relatedTarget, this)) {
        this.$.input.focus();
        return;
      }
      await this.dispatch('blur', this.statePath);
    }

    async onKeyup_(event) {
      if (event.key === 'Escape') {
        this.$.input.blur();
        return;
      }
      await this.dispatch('onKeyup', this.statePath, event.target.value);
      this.dispatchEvent(new CustomEvent('input-keyup', {
        detail: {
          key: event.key,
          value: this.query,
        },
      }));
    }

    async onClear_(event) {
      await this.dispatch('clear', this.statePath);
      this.dispatchEvent(new CustomEvent('clear'));
      this.dispatchEvent(new CustomEvent('option-select', {
        bubbles: true,
        composed: true,
      }));
    }
  }

  MenuInput.inputValue = (isFocused, query, selectedOptions) => {
    if (isFocused) return query;
    if (selectedOptions === undefined) return '';
    if (selectedOptions.length === 0) return '';
    if (selectedOptions.length === 1) return selectedOptions[0];
    return `[${selectedOptions.length} selected]`;
  };

  MenuInput.State = {
    ...cp.OptionGroup.RootState,
    ...cp.OptionGroup.State,
    alwaysEnabled: options => options.alwaysEnabled !== false,
    focusTimestamp: options => undefined,
    hasBeenOpened: options => false,
    label: options => options.label || '',
    requireSingle: options => options.requireSingle || false,
    required: options => options.required || false,
  };

  MenuInput.buildState = options => cp.buildState(
      MenuInput.State, options);

  MenuInput.properties = {
    ...cp.buildProperties('state', MenuInput.State),
    largeDom: {statePath: 'largeDom'},
    rootFocusTimestamp: {statePath: 'focusTimestamp'},
    isFocused: {computed: 'isEqual_(focusTimestamp, rootFocusTimestamp)'},
  };

  MenuInput.observers = ['observeIsFocused_(isFocused)'];

  MenuInput.actions = {
    focus: inputStatePath => async(dispatch, getState) => {
      dispatch({
        type: MenuInput.reducers.focus.name,
        // NOT "statePath"! Redux.statePathReducer would mess that up.
        inputStatePath,
      });
    },

    blurAll: () => async(dispatch, getState) => {
      dispatch({type: MenuInput.reducers.focus.name});
    },

    blur: statePath => async(dispatch, getState) => {
      dispatch(Redux.UPDATE(statePath, {
        focusTimestamp: window.performance.now(),
        query: '',
      }));
    },

    clear: statePath => async(dispatch, getState) => {
      dispatch(Redux.UPDATE(statePath, {query: '', selectedOptions: []}));
      cp.MenuInput.actions.focus(statePath)(dispatch, getState);
    },

    onKeyup: (statePath, query) => async(dispatch, getState) => {
      dispatch(Redux.UPDATE(statePath, {query}));
    },
  };

  MenuInput.reducers = {
    focus: (rootState, {inputStatePath}, rootStateAgain) => {
      const focusTimestamp = window.performance.now();
      rootState = {...rootState, focusTimestamp};
      if (!inputStatePath) return rootState; // Blur all menu-inputs
      return cp.setImmutable(rootState, inputStatePath, inputState => {
        return {...inputState, focusTimestamp, hasBeenOpened: true};
      });
    },
  };

  cp.ElementBase.register(MenuInput);
  return {MenuInput};
});
