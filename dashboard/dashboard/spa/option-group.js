/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './cp-checkbox.js';
import './expand-button.js';
import '@polymer/polymer/lib/elements/dom-if.js';
import '@polymer/polymer/lib/elements/dom-repeat.js';
import ElementBase from './element-base.js';
import {get} from '@polymer/polymer/lib/utils/path.js';
import {html} from '@polymer/polymer/polymer-element.js';

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
      query: '',
    };
  }

  static get template() {
    return html`
      <style>
        :host {
          display: flex;
          flex-direction: column;
        }

        .row {
          align-items: center;
          display: flex;
          margin: 1px 0 1px 8px;
        }

        .row[indent] {
          margin-left: 60px;
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
          flex-shrink: 0;
        }
      </style>

      <dom-repeat items="[[options]]" as="option"
                                index-as="optionIndex">
        <template>
          <dom-if if="[[matches_(option, query)]]">
            <template>
              <div class="row" indent$="[[indentRow_(option)]]">
                <dom-if if="[[option.options]]">
                  <template>
                    <expand-button
                        state-path="[[statePath]].options.[[optionIndex]]"
                        tabindex="0">
                      [[countDescendents_(option.options)]]
                    </expand-button>
                  </template>
                </dom-if>

                <cp-checkbox
                    checked="[[isSelected_(option, selectedOptions)]]"
                    disabled="[[option.disabled]]"
                    tabindex="0"
                    on-change="onSelect_">
                  [[label_(option)]]
                </cp-checkbox>
              </div>

              <dom-if if="[[shouldStampSubOptions_(option, query)]]">
                <template>
                  <iron-collapse opened="[[isExpanded_(option, query)]]">
                    <option-group
                        state-path="[[statePath]].options.[[optionIndex]]"
                        root-state-path="[[rootStatePath]]">
                    </option-group>
                  </iron-collapse>
                </template>
              </dom-if>
            </template>
          </dom-if>
        </template>
      </dom-repeat>
    `;
  }

  stateChanged(rootState) {
    if (!this.statePath || !this.rootStatePath) return;
    this.setProperties({
      ...get(rootState, this.rootStatePath),
      ...get(rootState, this.statePath),
    });
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

  async onSelect_(event) {
    await this.dispatch('select', this.rootStatePath, event.model.option);
    this.dispatchEvent(new CustomEvent('option-select', {
      bubbles: true,
      composed: true,
    }));
  }
}

// Groups with fewer options than this will always be stamped to the DOM so
// that they display quickly. Groups with more options than this will only be
// stamped to the DOM when the user expands the group in order to save memory.
OptionGroup.TOO_MANY_OPTIONS = 20;

OptionGroup.getAnyGroups = options =>
  (options || []).filter(o => o.options).length > 0;

OptionGroup.matches = (option, queryParts) => {
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
};

OptionGroup.getValuesFromOption = option => {
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
};

OptionGroup.countDescendents = options => {
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
};

OptionGroup.groupValues = (names, isExpanded) => {
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
};

OptionGroup.simplifyOption = option => {
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
};

OptionGroup.actions = {
  select: (statePath, option) => async(dispatch, getState) => {
    dispatch({
      type: OptionGroup.reducers.select.name,
      statePath,
      option,
    });
  },
};

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
