/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import OptionGroup from './option-group.js';
import {ElementBase, STORE} from './element-base.js';
import {get} from './utils.js';
import {html, css} from 'lit-element';

export default class MemoryComponents extends ElementBase {
  static get is() { return 'memory-components'; }

  static get properties() {
    return {
      ...OptionGroup.properties,
      columns: Array,
    };
  }

  static buildState(options = {}) {
    return {
      ...OptionGroup.buildState(options),
      columns: MemoryComponents.buildColumns(
          options.options || [], options.selectedOptions || []),
    };
  }

  static get styles() {
    return css`
      :host {
        display: flex;
      }

      .column {
        border-bottom: 1px solid var(--primary-color-dark, blue);
        margin-bottom: 4px;
        max-height: 143px;
        overflow-y: auto;
      }
    `;
  }

  render() {
    return html`${this.columns.map((column, columnIndex) => html`
      <div class="column">
        <option-group
            .statePath="${this.statePath}.columns.${columnIndex}"
            .rootStatePath="${this.statePath}.columns.${columnIndex}"
            @option-select="${this.onColumnSelect_}">
        </option-group>
      </div>
    `)}`;
  }

  stateChanged(rootState) {
    if (!this.statePath) return;

    const oldOptions = this.options;
    const oldSelectedOptions = this.selectedOptions;
    Object.assign(this, get(rootState, this.statePath));
    if (this.options && this.selectedOptions &&
        (this.options !== oldOptions ||
         this.selectedOptions !== oldSelectedOptions)) {
      STORE.dispatch({
        type: MemoryComponents.reducers.buildColumns.name,
        statePath: this.statePath,
      });
    }
  }

  async onColumnSelect_(event) {
    STORE.dispatch({
      type: MemoryComponents.reducers.onColumnSelect.name,
      statePath: this.statePath,
    });
    this.dispatchEvent(new CustomEvent('option-select', {
      bubbles: true,
      composed: true,
    }));
  }
}

MemoryComponents.buildColumns = (options, selectedOptions) => {
  if (!options || !options.length ||
      !selectedOptions || !selectedOptions.length) {
    return [];
  }
  const columnOptions = [];
  for (const option of options) {
    for (const name of OptionGroup.getValuesFromOption(option)) {
      const columns = MemoryComponents.parseColumns(name);
      while (columnOptions.length < columns.length) {
        columnOptions.push(new Set());
      }
      for (let i = 0; i < columns.length; ++i) {
        columnOptions[i].add(columns[i]);
      }
    }
  }

  const selectedColumns = [];
  while (selectedColumns.length < columnOptions.length) {
    selectedColumns.push(new Set());
  }
  for (const name of selectedOptions) {
    const columns = MemoryComponents.parseColumns(name);
    if (columns.length > selectedColumns.length) return [];
    for (let i = 0; i < columns.length; ++i) {
      selectedColumns[i].add(columns[i]);
    }
  }

  return columnOptions.map((options, columnIndex) => {
    return {
      options: OptionGroup.groupValues([...options].sort()),
      selectedOptions: [...selectedColumns[columnIndex]],
    };
  });
};

MemoryComponents.reducers = {
  buildColumns: (state, action, rootState) => {
    if (!state) return state;
    return {
      ...state,
      columns: MemoryComponents.buildColumns(
          state.options, state.selectedOptions),
    };
  },

  onColumnSelect: (state, action, rootState) => {
    // Remove all memory measurements from state.selectedOptions
    const selectedOptions = state.selectedOptions.filter(v =>
      !v.startsWith('memory:'));

    // Add all options whose columns are all selected.
    const selectedColumns = state.columns.map(column =>
      column.selectedOptions);
    for (const option of state.options) {
      for (const value of OptionGroup.getValuesFromOption(option)) {
        if (MemoryComponents.allColumnsSelected(value, selectedColumns)) {
          selectedOptions.push(value);
        }
      }
    }

    return {...state, selectedOptions};
  },
};

MemoryComponents.parseColumns = name => {
  // See getNumericName in memoryMetric:
  // /tracing/tracing/metrics/system_health/memory_metric.html
  const parts = name.split(':');
  if (parts[0] !== 'memory') return [];
  if (parts.length < 5) return [];

  const browser = parts[1];
  let process = parts[2].replace(/_processe?/, '');
  if (process === 'alls') process = 'all';
  const source = parts[3].replace(/^reported_/, '');
  let component = parts.slice(4, parts.length - 1).join(':').replace(
      /system_memory/, 'system');
  if (!component) component = 'overall';
  const size = parts[parts.length - 1].replace(/_size(_\w)?$/, '');
  return [browser, process, source, component, size];
};

MemoryComponents.allColumnsSelected = (name, selectedColumns) => {
  const columns = MemoryComponents.parseColumns(name);
  if (columns.length === 0) return false;
  for (let i = 0; i < columns.length; ++i) {
    if (!selectedColumns[i].includes(columns[i])) return false;
  }
  return true;
};

ElementBase.register(MemoryComponents);
