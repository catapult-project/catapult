/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './cp-icon.js';
import './cp-input.js';
import './raised-button.js';
import ReportTemplateRequest from './report-template-request.js';
import TimeseriesDescriptor from './timeseries-descriptor.js';
import {ElementBase, STORE} from './element-base.js';
import {TOGGLE, UPDATE} from './simple-redux.js';
import {get} from './utils.js';
import {html, css} from 'lit-element';

export default class ReportTemplate extends ElementBase {
  static get is() { return 'report-template'; }

  static get properties() {
    return {
      statePath: String,
      id: Number,
      name: String,
      owners: Array,
      rows: Array,
      statistic: Object,
      url: String,
    };
  }

  static buildState(options = {}) {
    return {
      id: options.id || 0,
      name: options.name || '',
      owners: options.owners || [],
      rows: options.rows || [],
      statistic: options.statistic,
      url: options.url || '',
    };
  }

  static get styles() {
    return css`
      :host {
        padding: 16px;
      }
      table {
        border-collapse: collapse;
        margin-top: 16px;
      }

      table[placeholder] {
        color: var(--neutral-color-dark, grey);
      }

      h2 {
        text-align: center;
        margin: 0;
      }

      .name_column {
        text-align: left;
      }

      td, th {
        padding: 4px;
        vertical-align: top;
      }

      .edit_form_controls {
        display: flex;
        justify-content: space-evenly;
      }

      .edit_form_controls cp-input {
        width: 250px;
      }

      .edit_form_controls menu-input:not(:last-child),
      .edit_form_controls cp-input:not(:last-child) {
        margin-right: 8px;
      }

      cp-input {
        margin-top: 12px;
      }

      #cancel,
      #save {
        flex-grow: 1;
      }

      .row_button {
        vertical-align: middle;
      }

      .row_button cp-icon {
        cursor: pointer;
      }

      .error {
        color: var(--error-color, red);
      }
    `;
  }

  render() {
    return html`
      <div class="edit_form_controls">
        <div>
          <cp-input
              id="name"
              error="${!this.name}"
              label="Report Name"
              value="${this.name}"
              @keyup="${this.onTemplateNameKeyUp_}">
          </cp-input>
          <span class="error" ?hidden="${!!this.name}">
            required
          </span>
        </div>

        <div>
          <cp-input
              error="${!this.owners}"
              label="Owners"
              value="${this.owners}"
              @keyup="${this.onTemplateOwnersKeyUp_}">
          </cp-input>
          <span class="error" ?hidden="${!!this.owners}">
              comma-separate list of complete email addresses
          </span>
        </div>

        <menu-input .statePath="${this.statePath}.statistic">
        </menu-input>

        <div>
          <cp-input
              label="Documentation"
              value="${this.url}"
              @keyup="${this.onTemplateUrlKeyUp_}">
          </cp-input>
        </div>
      </div>

      <table>
        <tbody>
          ${this.rows.map((row, rowIndex) => html`
            <tr>
              <td>
                <cp-input
                    label="Label"
                    error="${!row.label}"
                    value="${row.label}"
                    @keyup="${event =>
    this.onTemplateRowLabelKeyUp_(event, rowIndex)}">
                </cp-input>
                <span class="error" ?hidden="${!!row.label}">
                  required
                </span>
              </td>
              <td>
                <timeseries-descriptor
                    .statePath="${this.statePath}.rows.${rowIndex}">
                </timeseries-descriptor>
              </td>
              <td class="row_button">
                <cp-icon
                    icon="add"
                    @click="${event => this.onTemplateAddRow_(rowIndex)}">
                </cp-icon>
              </td>
              <td class="row_button">
                ${(this.rows.length === 1) ? '' : html`
                  <cp-icon
                      icon="remove"
                      @click="${event => this.onTemplateRemoveRow_(rowIndex)}">
                  </cp-icon>
                `}
              </td>
            </tr>
          `)}
        </tbody>
      </table>

      <div class="edit_form_controls">
        <raised-button
            id="cancel"
            @click="${this.onCancel_}">
          <cp-icon icon="cancel"></cp-icon>
          Cancel
        </raised-button>

        <raised-button
            id="save"
            ?disabled="${!ReportTemplate.canSave(
      this.name, this.owners, this.statistic, this.rows)}"
            @click="${this.onTemplateSave_}">
          <cp-icon icon="save"></cp-icon>
          Save
        </raised-button>
      </div>
    `;
  }

  async onCancel_(event) {
    await STORE.dispatch(TOGGLE(this.statePath + '.isEditing'));
  }

  async onTemplateNameKeyUp_(event) {
    await STORE.dispatch(UPDATE(this.statePath, {
      name: event.target.value,
    }));
  }

  async onTemplateOwnersKeyUp_(event) {
    await STORE.dispatch(UPDATE(this.statePath, {
      owners: event.target.value,
    }));
  }

  async onTemplateUrlKeyUp_(event) {
    await STORE.dispatch(UPDATE(this.statePath, {
      url: event.target.value,
    }));
  }

  async onTemplateRowLabelKeyUp_(event, rowIndex) {
    await STORE.dispatch(UPDATE(
        this.statePath + '.rows.' + rowIndex,
        {label: event.target.value}));
  }

  async onTemplateRemoveRow_(rowIndex) {
    await STORE.dispatch({
      type: ReportTemplate.reducers.removeRow.name,
      statePath: this.statePath,
      rowIndex,
    });
  }

  async onTemplateAddRow_(rowIndex) {
    await STORE.dispatch({
      type: ReportTemplate.reducers.addRow.name,
      statePath: this.statePath,
      rowIndex,
    });
  }

  async onTemplateSave_(event) {
    await ReportTemplate.save(this.statePath);
    this.dispatchEvent(new CustomEvent('save', {
      bubbles: true,
      composed: true,
    }));
  }

  static async save(statePath) {
    STORE.dispatch(UPDATE(statePath, {isLoading: true, isEditing: false}));
    const table = get(STORE.getState(), statePath);
    const request = new ReportTemplateRequest({
      id: table.id,
      name: table.name,
      owners: table.owners.split(',').map(o => o.replace(/ /g, '')),
      url: table.url,
      statistics: table.statistic.selectedOptions,
      rows: table.rows.map(row => {
        return {
          label: row.label,
          suites: row.suite.selectedOptions,
          measurement: row.measurement.selectedOptions[0],
          bots: row.bot.selectedOptions,
          cases: row.case.selectedOptions,
        };
      }),
    });
    const reportTemplateInfos = await request.response;
    STORE.dispatch(UPDATE('', {reportTemplateInfos}));
  }
}

ReportTemplate.reducers = {
  removeRow: (state, {rowIndex}, rootState) => {
    const rows = [...state.rows];
    rows.splice(rowIndex, 1);
    return {...state, rows};
  },

  addRow: (table, action, rootState) => {
    const contextRow = table.rows[action.rowIndex];
    const newRow = ReportTemplate.newTemplateRow({
      suites: [...contextRow.suite.selectedOptions],
      bots: [...contextRow.bot.selectedOptions],
      cases: [...contextRow.case.selectedOptions],
    });
    const rows = [...table.rows];
    rows.splice(action.rowIndex + 1, 0, newRow);
    return {...table, rows};
  },
};

ReportTemplate.newTemplateRow = ({
  label, suites, measurement, bots, cases,
}) => {
  return {
    label: label || '',
    ...TimeseriesDescriptor.buildState({
      suite: {
        canAggregate: false,
        isAggregated: true,
        required: true,
        selectedOptions: suites || [],
      },
      measurement: {
        requireSingle: true,
        required: true,
        selectedOptions: measurement ? [measurement] : [],
      },
      bot: {
        canAggregate: false,
        isAggregated: true,
        required: true,
        selectedOptions: bots || [],
      },
      case: {
        canAggregate: false,
        isAggregated: true,
        selectedOptions: cases || [],
      },
    }),
  };
};

ReportTemplate.canSave = (name, owners, statistic, rows) => {
  if (!name || !owners || !statistic || !rows ||
      statistic.selectedOptions.length === 0) {
    return false;
  }
  for (const row of rows) {
    if (!row.label || !row.suite || !row.measurement || !row.bot ||
        row.suite.selectedOptions.length === 0 ||
        row.measurement.selectedOptions.length !== 1 ||
        row.bot.selectedOptions.length === 0) {
      return false;
    }
  }
  return true;
};

ElementBase.register(ReportTemplate);
