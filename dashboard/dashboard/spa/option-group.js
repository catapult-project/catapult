/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './cp-checkbox.js';
import './expand-button.js';
import {ElementBase, STORE} from './element-base.js';
import {get} from './utils.js';
import {html, css} from 'lit-element';

export default class OptionGroup extends ElementBase {
  static get is() { return 'option-group'; }

  static get properties() {
    return {
      statePath: String,

      // Elements of this array look like {
      //   isExpanded, label, options, value, valueLowerCase}.
      options: Array,

      optionValues: Array,

      rootStatePath: String,
      // Array of string values.
      selectedOptions: Array,

      cursor: String,

      // Set this to filter options. An option matches the query if its
      // valueLowerCase contains all of the space-separated parts of the query.
      query: String,
    };
  }

  static buildState(options = {}) {
    return {
      options: OptionGroup.groupValues(options.options || []),
      optionValues: options.options || new Set(),
      selectedOptions: options.selectedOptions || [],
      query: options.query || '',
      cursor: options.cursor || undefined,
    };
  }

  static get styles() {
    return css`
      :host {
        display: flex;
        flex-direction: column;
      }
      :host([hidden]) {
        display: none;
      }

      .row[cursor] {
        background-color: var(--focus-color, yellow);
      }

      .row {
        align-items: center;
        display: flex;
        margin: 1px 0 1px 8px;
      }

      .row[indent] {
        padding-left: 52px;
      }

      option-group {
        margin-left: 28px;
      }

      expand-button {
        align-items: center;
        border-radius: 0;
        height: 100%;
        justify-content: space-between;
        margin: 0;
        min-width: 0;
        padding: 0 8px 0 0;
        width: 44px;
        flex-shrink: 0;
      }

      cp-checkbox {
        flex-grow: 1;
        flex-shrink: 0;
        width: unset;
      }
    `;
  }

  renderOption(option, optionIndex) {
    if (!this.matches_(option, this.query)) return '';
    const statePath = `${this.statePath}.options.${optionIndex}`;
    return html`
      <div class="row"
          ?cursor="${this.cursor === statePath}"
          ?indent="${this.indentRow_(option)}">
        ${!option.options ? '' : html`
          <expand-button
              .statePath="${statePath}"
              tabindex="0">
            ${this.countDescendents_(option.options)}
          </expand-button>
        `}

        <cp-checkbox
            ?checked="${this.isSelected_(option, this.selectedOptions)}"
            ?disabled="${option.disabled}"
            tabindex="0"
            @change="${event => this.onSelect_(option)}">
          ${this.label_(option)}
        </cp-checkbox>
      </div>

      ${!this.shouldStampSubOptions_(option, this.query) ? '' : html`
        <option-group
            ?hidden="${!this.isExpanded_(option, this.query)}"
            .statePath="${this.statePath}.options.${optionIndex}"
            .rootStatePath="${this.rootStatePath}">
        </option-group>
      `}
    `;
  }

  render() {
    return html`${(this.options || []).map((option, optionIndex) =>
      this.renderOption(option, optionIndex))}`;
  }

  stateChanged(rootState) {
    if (!this.statePath || !this.rootStatePath) return;
    Object.assign(this, get(rootState, this.rootStatePath));
    Object.assign(this, get(rootState, this.statePath));
  }

  updated(changedProperties) {
    if (changedProperties.has('cursor') || changedProperties.has('query')) {
      const cursor = this.shadowRoot.querySelector('[cursor]');
      if (cursor) cursor.scrollIntoView({block: 'center', inline: 'center'});
    }
  }

  // There may be thousands of options in an option-group. It could cost a lot
  // of memory and CPU to stamp (create DOM for) all of them. That DOM may or
  // may not be needed, so we can speed up loading by waiting to stamp it
  // until the user needs it. OTOH, we can speed up interacting with the
  // option-group by pre-computing that DOM before the user needs it. This
  // method decides when to trade off loading latency versus responsivity
  // versus memory.
  shouldStampSubOptions_(option, query) {
    if (!option) return false;
    if (!option.options) return false;
    if (option.options.length < OptionGroup.TOO_MANY_OPTIONS) return true;
    return this.isExpanded_(option, query);
  }

  isExpanded_(option, query) {
    // Expand all groups after the user has entered a query, but don't expand
    // everything as soon as the user starts typing.
    return (query && (query.length > 1)) || (option && option.isExpanded);
  }

  matches_(option, query) {
    if (!query) return true;
    return OptionGroup.matches(option, query.toLocaleLowerCase().split(' '));
  }

  countDescendents_(options) {
    return OptionGroup.countDescendents(options);
  }

  isSelected_(option, selectedOptions) {
    if (!option || !selectedOptions) return false;
    for (const value of OptionGroup.getValuesFromOption(option)) {
      if (selectedOptions.includes(value)) return true;
    }
    return false;
  }

  label_(option) {
    if (typeof(option) === 'string') return option;
    return option.label;
  }

  indentRow_(option) {
    if (option.options) return false;
    return !this.isRoot_() || OptionGroup.getAnyGroups(this.options);
  }

  isRoot_() {
    return this.statePath === this.rootStatePath;
  }

  async onSelect_(option) {
    await STORE.dispatch({
      type: OptionGroup.reducers.select.name,
      statePath: this.rootStatePath,
      option,
    });
    this.dispatchEvent(new CustomEvent('option-select', {
      bubbles: true,
      composed: true,
    }));
  }

  static getAnyGroups(options) {
    return (options || []).filter(o => o.options).length > 0;
  }

  static matches(option, queryParts) {
    if (option.options) {
      for (const suboption of option.options) {
        if (OptionGroup.matches(suboption, queryParts)) return true;
      }
      return false;
    }
    if (option.valueLowerCase) {
      option = option.valueLowerCase;
    } else if (option.value) {
      option = option.value;
    } else {
      option = option.toLocaleLowerCase();
    }
    for (const part of queryParts) {
      if (!option.includes(part)) return false;
    }
    return true;
  }

  static getValuesFromOption(option) {
    if (option === undefined) return [];
    if (typeof(option) === 'string') return [option];
    if (option.options) {
      const values = [];
      if (option.value) {
        values.push(option.value);
      }
      for (const child of option.options) {
        values.push(...OptionGroup.getValuesFromOption(child));
      }
      return values;
    }
    if (option.value) return [option.value];
    return [];
  }

  static countDescendents(options) {
    let count = 0;
    for (const option of options) {
      if (option.options) {
        count += OptionGroup.countDescendents(option.options);
        if (option.value) {
          count += 1;
        }
      } else {
        count += 1;
      }
    }
    return count;
  }

  static groupValues(names, isExpanded) {
    isExpanded = isExpanded || false;
    const options = [];
    for (const name of names) {
      const parts = name.split(':');
      let parent = options;
      for (let i = 0; i < parts.length; ++i) {
        const part = parts[i];

        let found = false;
        for (const option of parent) {
          if (option.label === part) {
            if (i === parts.length - 1) {
              option.options.push({
                isExpanded,
                label: part,
                options: [],
                value: name,
                valueLowerCase: name.toLocaleLowerCase(),
              });
            } else {
              parent = option.options;
            }
            found = true;
            break;
          }
        }

        if (!found) {
          if (i === parts.length - 1) {
            parent.push({
              isExpanded,
              label: part,
              options: [],
              value: name,
              valueLowerCase: name.toLocaleLowerCase(),
            });
          } else {
            const option = {
              isExpanded,
              label: part,
              options: [],
            };
            parent.push(option);
            parent = option.options;
          }
        }
      }
    }
    return options.map(OptionGroup.simplifyOption);
  }

  static simplifyOption(option) {
    if (!option.options) {
      return option;
    }
    if (option.options.length === 0) {
      return {
        label: option.label,
        value: option.value,
        valueLowerCase: option.valueLowerCase,
      };
    }
    if (option.options.length > 1 ||
        option.value) {
      return {
        ...option,
        options: option.options.map(OptionGroup.simplifyOption),
      };
    }
    if (option.options[0].options) {
      return OptionGroup.simplifyOption({
        isExpanded: false,
        options: option.options[0].options,
        label: option.label + ':' + option.options[0].label,
        value: option.options[0].value,
        valueLowerCase: option.options[0].valueLowerCase,
      });
    }
    if (option.options[0].label) {
      return {
        ...option.options[0],
        label: option.label + ':' + option.options[0].label,
      };
    }
    return option.options[0];
  }
}

// Groups with fewer options than this will always be stamped to the DOM so
// that they display quickly. Groups with more options than this will only be
// stamped to the DOM when the user expands the group in order to save memory.
OptionGroup.TOO_MANY_OPTIONS = 20;

OptionGroup.reducers = {
  select: (state, action, rootState) => {
    const selectedOptions = new Set(state.selectedOptions);

    // action.option is either
    // a string to toggle
    // OR an object without an array of sub options but with a value to toggle
    // OR an object without a value but with an array of sub options to toggle
    // collectively
    // OR an object with both a value and an array of sub options; use
    // tristate logic to toggle either the value or the sub options.

    let value;
    if (typeof(action.option) === 'string') {
      value = action.option;
    } else if (action.option.value &&
        (!action.option.options ||
          !selectedOptions.has(action.option.value))) {
      value = action.option.value;
    } else {
      const values = OptionGroup.getValuesFromOption(action.option);
      const selectedValues = values.filter(value =>
        value !== action.option.value && selectedOptions.has(value));
      if (selectedValues.length > 0) {
        for (const value of values) selectedOptions.delete(value);
      } else {
        for (const value of values) selectedOptions.add(value);
      }
    }

    if (value) {
      if (selectedOptions.has(value)) {
        selectedOptions.delete(value);
      } else {
        selectedOptions.add(value);
      }
    }
    return {...state, selectedOptions: [...selectedOptions]};
  },
};

ElementBase.register(OptionGroup);
