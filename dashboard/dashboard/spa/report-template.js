/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

export default class ReportTemplate extends cp.ElementBase {
  static get template() {
    return Polymer.html`
      <style>
        :host {
          padding: 16px;
        }
        table {
          border-collapse: collapse;
          margin-top: 16px;
        }

        table[placeholder] {
          color: var(--neutral-color-dark);
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

        .row_button iron-icon {
          cursor: pointer;
          height: var(--icon-size, 1em);
          width: var(--icon-size, 1em);
        }

        .error {
          color: var(--error-color);
        }
      </style>

      <div class="edit_form_controls">
        <div>
          <cp-input
              id="name"
              error$="[[isEmpty_(name)]]"
              label="Report Name"
              value="[[name]]"
              on-keyup="onTemplateNameKeyUp_">
          </cp-input>
          <span class="error" hidden$="[[!isEmpty_(name)]]">
            required
          </span>
        </div>

        <div>
          <cp-input
              error$="[[isEmpty_(owners)]]"
              label="Owners"
              value="[[owners]]"
              on-keyup="onTemplateOwnersKeyUp_">
          </cp-input>
          <span class="error" hidden$="[[!isEmpty_(owners)]]">
              comma-separate list of complete email addresses
          </span>
        </div>

        <menu-input state-path="[[statePath]].statistic">
        </menu-input>

        <div>
          <cp-input
              label="Documentation"
              value="[[url]]"
              on-keyup="onTemplateUrlKeyUp_">
          </cp-input>
        </div>
      </div>

      <table>
        <tbody>
          <template is="dom-repeat" items="[[rows]]" as="row"
                                    index-as="rowIndex">
            <tr>
              <td>
                <cp-input
                    label="Label"
                    error$="[[isEmpty_(row.label)]]"
                    value="[[row.label]]"
                    on-keyup="onTemplateRowLabelKeyUp_">
                </cp-input>
                <span class="error" hidden$="[[!isEmpty_(row.label)]]">
                  required
                </span>
              </td>
              <td>
                <timeseries-descriptor
                    state-path="[[statePath]].rows.[[rowIndex]]">
                </timeseries-descriptor>
              </td>
              <td class="row_button">
                <iron-icon
                    icon="cp:add"
                    on-click="onTemplateAddRow_">
                </iron-icon>
              </td>
              <td class="row_button">
                <template is="dom-if" if="[[isMultiple_(rows)]]">
                  <iron-icon
                      icon="cp:remove"
                      on-click="onTemplateRemoveRow_">
                  </iron-icon>
                </template>
              </td>
            </tr>
          </template>
        </tbody>
      </table>

      <div class="edit_form_controls">
        <raised-button
            id="cancel"
            on-click="onCancel_">
          <iron-icon icon="cp:cancel">
          </iron-icon>
          Cancel
        </raised-button>

        <raised-button
            id="save"
            disabled$="[[!canSave_(name, owners, statistic, rows)]]"
            on-click="onTemplateSave_">
          <iron-icon icon="cp:save">
          </iron-icon>
          Save
        </raised-button>
      </div>
    `;
  }

  canSave_(name, owners, statistic, rows) {
    return ReportTemplate.canSave(name, owners, statistic, rows);
  }

  async onCancel_(event) {
    await this.dispatch(Redux.TOGGLE(this.statePath + '.isEditing'));
  }

  async onTemplateNameKeyUp_(event) {
    await this.dispatch(Redux.UPDATE(this.statePath, {
      name: event.target.value,
    }));
  }

  async onTemplateOwnersKeyUp_(event) {
    await this.dispatch(Redux.UPDATE(this.statePath, {
      owners: event.target.value,
    }));
  }

  async onTemplateUrlKeyUp_(event) {
    await this.dispatch(Redux.UPDATE(this.statePath, {
      url: event.target.value,
    }));
  }

  async onTemplateRowLabelKeyUp_(event) {
    await this.dispatch(Redux.UPDATE(
        this.statePath + '.rows.' + event.model.rowIndex,
        {label: event.target.value}));
  }

  async onTemplateRemoveRow_(event) {
    await this.dispatch('removeRow', this.statePath, event.model.rowIndex);
  }

  async onTemplateAddRow_(event) {
    await this.dispatch('addRow', this.statePath, event.model.rowIndex);
  }

  async onTemplateSave_(event) {
    await this.dispatch('save', this.statePath);
    this.dispatchEvent(new CustomEvent('save', {
      bubbles: true,
      composed: true,
    }));
  }
}

ReportTemplate.State = {
  id: options => options.id || 0,
  name: options => options.name || '',
  owners: options => options.owners || [],
  rows: options => options.rows || [],
  statistic: options => options.statistic,
  url: options => options.url || '',
};

ReportTemplate.buildState = options => cp.buildState(
    ReportTemplate.State, options);

ReportTemplate.properties = {
  ...cp.buildProperties('state', ReportTemplate.State),
};

ReportTemplate.actions = {
  removeRow: (statePath, rowIndex) =>
    async(dispatch, getState) => {
      dispatch({
        type: ReportTemplate.reducers.removeRow.name,
        statePath,
        rowIndex,
      });
    },

  addRow: (statePath, rowIndex) =>
    async(dispatch, getState) => {
      dispatch({
        type: ReportTemplate.reducers.addRow.name,
        statePath,
        rowIndex,
      });
    },

  save: statePath => async(dispatch, getState) => {
    dispatch(Redux.UPDATE(statePath, {isLoading: true, isEditing: false}));
    const table = Polymer.Path.get(getState(), statePath);
    const request = new cp.ReportTemplateRequest({
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
    dispatch(Redux.UPDATE('', {reportTemplateInfos}));
  },
};

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
    ...cp.TimeseriesDescriptor.buildState({
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

cp.ElementBase.register(ReportTemplate);
