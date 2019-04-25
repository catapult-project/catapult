/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './cp-checkbox.js';
import './expand-button.js';
import './column-head.js';
import './scalar-span.js';
import ElementBase from './element-base.js';

import {
  breakWords,
  buildProperties,
  buildState,
  setImmutable,
} from './utils.js';

export default class AlertsTable extends ElementBase {
  static get is() { return 'alerts-table'; }

  static get template() {
    return Polymer.html`
      <style>
        #cat {
          display: block;
          height: 300px;
          width: 300px;
        }

        :host {
          --min-table-height: 122px;
          --non-table-height: 483px;
        }

        #scroll {
          max-height: calc(100vh - var(--non-table-height));
          margin: 0;
          overflow-y: auto;
          overflow-x: hidden;
        }

        @media screen and (max-height: calc(var(--min-table-height) +
                                            var(--non-table-height))) {
          #scroll {
            max-height: var(--min-table-height);
          }
        }

        table {
          border-collapse: collapse;
          width: 100%;
        }

        table[is-placeholder] {
          color: var(--neutral-color-dark, grey);
        }

        th {
          padding: 8px;
          white-space: nowrap;
        }

        th.checkbox {
          padding-left: 4px;
          text-align: left;
        }

        td {
          padding: 4px;
        }

        tbody tr:hover {
          background: #eee;
        }

        td:last-child {
          padding-right: 0;
        }

        expand-button {
          align-items: center;
          justify-content: flex-end;
          margin-right: 16px;
        }

        tbody {
          border-color: var(--background-color, white);
          border-style: solid;
          border-width: 0 8px;
          transition: border-width var(--transition-short, 0.2s);
        }

        tbody[expandedGroup] {
          border-color: var(--primary-color-light, lightblue);
          border-width: 8px;
        }
      </style>

      <template is="dom-if" if="[[allTriaged_(alertGroups, showingTriaged)]]">
        <center>
          All alerts triaged!
          <iron-icon id="cat" icon="cp-big:cat">
          </iron-icon>
        </center>
      </template>

      <template is="dom-if" if="[[!allTriaged_(
          alertGroups, showingTriaged)]]">
        <div id="scroll">
          <table is-placeholder$="[[areAlertGroupsPlaceholders]]">
            <thead>
              <tr>
                <th>
                  <column-head
                      name="count"
                      sort-column="[[sortColumn]]"
                      sort-descending="[[sortDescending]]"
                      disabled="[[areAlertGroupsPlaceholders]]"
                      on-click="onSort_">
                    Count
                  </column-head>
                </th>

                <template is="dom-if" if="[[showTriagedColumn]]">
                  <th>
                    <column-head
                        name="triaged"
                        sort-column="[[sortColumn]]"
                        sort-descending="[[sortDescending]]"
                        disabled="[[areAlertGroupsPlaceholders]]"
                        on-click="onSort_">
                      Triaged
                    </column-head>
                  </th>
                </template>

                <th class="checkbox">
                  <cp-checkbox
                      checked="[[anySelectedAlerts_(alertGroups)]]"
                      disabled="[[areAlertGroupsPlaceholders]]"
                      on-change="onSelectAll_">
                  </cp-checkbox>
                </th>

                <template is="dom-if" if="[[showBugColumn]]">
                  <th>
                    <column-head
                        name="bugId"
                        sort-column="[[sortColumn]]"
                        sort-descending="[[sortDescending]]"
                        disabled="[[areAlertGroupsPlaceholders]]"
                        on-click="onSort_">
                      Bug
                    </column-head>
                  </th>
                </template>

                <th>
                  <column-head
                      name="startRevision"
                      sort-column="[[sortColumn]]"
                      sort-descending="[[sortDescending]]"
                      disabled="[[areAlertGroupsPlaceholders]]"
                      on-click="onSort_">
                    Revisions
                  </column-head>
                </th>

                <th>
                  <column-head
                      name="suite"
                      sort-column="[[sortColumn]]"
                      sort-descending="[[sortDescending]]"
                      disabled="[[areAlertGroupsPlaceholders]]"
                      on-click="onSort_">
                    Suite
                  </column-head>
                </th>

                <th>
                  <column-head
                      name="measurement"
                      sort-column="[[sortColumn]]"
                      sort-descending="[[sortDescending]]"
                      disabled="[[areAlertGroupsPlaceholders]]"
                      on-click="onSort_">
                    Measurement
                  </column-head>
                </th>

                <template is="dom-if" if="[[showMasterColumn]]">
                  <th>
                    <column-head
                        name="master"
                        sort-column="[[sortColumn]]"
                        sort-descending="[[sortDescending]]"
                        disabled="[[areAlertGroupsPlaceholders]]"
                        on-click="onSort_">
                      Master
                    </column-head>
                  </th>
                </template>

                <th>
                  <column-head
                      name="bot"
                      sort-column="[[sortColumn]]"
                      sort-descending="[[sortDescending]]"
                      disabled="[[areAlertGroupsPlaceholders]]"
                      on-click="onSort_">
                    Bot
                  </column-head>
                </th>

                <template is="dom-if" if="[[showCaseColumn]]">
                  <th>
                    <column-head
                        name="case"
                        sort-column="[[sortColumn]]"
                        sort-descending="[[sortDescending]]"
                        disabled="[[areAlertGroupsPlaceholders]]"
                        on-click="onSort_">
                      Case
                    </column-head>
                  </th>
                </template>

                <th>
                  <column-head
                      name="deltaValue"
                      sort-column="[[sortColumn]]"
                      sort-descending="[[sortDescending]]"
                      disabled="[[areAlertGroupsPlaceholders]]"
                      on-click="onSort_">
                    Delta
                  </column-head>
                </th>

                <th>
                  <column-head
                      name="percentDeltaValue"
                      sort-column="[[sortColumn]]"
                      sort-descending="[[sortDescending]]"
                      disabled="[[areAlertGroupsPlaceholders]]"
                      on-click="onSort_">
                    Delta %
                  </column-head>
                </th>
              </tr>
            </thead>

            <template is="dom-repeat" items="[[alertGroups]]" as="alertGroup"
                                      index-as="alertGroupIndex">
              <tbody expandedGroup$="[[isExpandedGroup_(
                  alertGroup.isExpanded, alertGroup.triaged.isExpanded)]]">
                <template is="dom-repeat" items="[[alertGroup.alerts]]"
                    as="alert" index-as="alertIndex">
                  <template is="dom-if" if="[[shouldDisplayAlert_(
                      areAlertGroupsPlaceholders, showingTriaged, alertGroup,
                      alertIndex, alertGroup.triaged.isExpanded)]]">
                    <tr on-click="onRowClick_">

                      <td>
                        <template is="dom-if"
                            if="[[shouldDisplayExpandGroupButton_(
                              alertGroup, alertIndex, showingTriaged,
                              sortColumn, sortDescending)]]">
                          <expand-button
                    state-path="[[statePath]].alertGroups.[[alertGroupIndex]]">
                            [[getExpandGroupButtonLabel_(
                              alertGroup, showingTriaged)]]
                          </expand-button>
                        </template>
                      </td>

                      <template is="dom-if" if="[[showTriagedColumn]]">
                        <td>
                          <template is="dom-if"
    if="[[shouldDisplayExpandTriagedButton_(showingTriaged, alertGroup,
      alertIndex, sortColumn, sortDescending)]]">
                            <expand-button
    state-path="[[statePath]].alertGroups.[[alertGroupIndex]].triaged">
                              [[alertGroup.triaged.count]]
                            </expand-button>
                          </template>
                        </td>
                      </template>

                      <td>
                        <cp-checkbox
                            checked="[[alert.isSelected]]"
                            disabled="[[areAlertGroupsPlaceholders]]"
                            on-change="onSelect_">
                          <template is="dom-if"
    if="[[shouldDisplaySelectedCount_(showingTriaged, alertGroup, alertIndex,
      sortColumn, sortDescending)]]">
                            [[selectedCount_(alertGroup)]]
                          </template>
                        </cp-checkbox>
                      </td>

                      <template is="dom-if" if="[[showBugColumn]]">
                        <td>
                          <template is="dom-if" if="[[!isEqual_(
                              alert.bugId, '')]]">
                            <template is="dom-if"
    if="[[areAlertGroupsPlaceholders]]">
                              [[alert.bugId]]
                            </template>
                            <template is="dom-if"
    if="[[!areAlertGroupsPlaceholders]]">
                              <template is="dom-if"
    if="[[isAlertIgnored_(alert.bugId)]]">
                                ignored
                              </template>
                              <template is="dom-if"
    if="[[!isAlertIgnored_(alert.bugId)]]">
                                <a href="https://crbug.com/[[alert.bugId]]" target="_blank">
                                  [[alert.bugId]]
                                </a>
                              </template>
                            </template>
                          </template>
                        </td>
                      </template>

                      <td>
                        <template is="dom-if"
    if="[[alertRevisionHref_(alert)]]">
                          <a href="[[alertRevisionHref_(alert)]]"
    target="_blank">
                            [[alertRevisionString_(alert)]]
                          </a>
                        </template>
                        <template is="dom-if"
    if="[[!alertRevisionHref_(alert)]]">
                          [[alertRevisionString_(alert)]]
                        </template>
                      </td>

                      <td style$="color: [[alert.color]];">
                        [[breakWords_(alert.suite)]]
                      </td>
                      <td style$="color: [[alert.color]];">
                        [[breakWords_(alert.measurement)]]
                      </td>

                      <template is="dom-if" if="[[showMasterColumn]]">
                        <td style$="color: [[alert.color]];">
                          [[alert.master]]
                        </td>
                      </template>

                      <td style$="color: [[alert.color]];">
                        [[alert.bot]]
                      </td>

                      <template is="dom-if" if="[[showCaseColumn]]">
                        <td style$="color: [[alert.color]];">
                          [[breakWords_(alert.case)]]
                        </td>
                      </template>

                      <td>
                        <scalar-span
                            value="[[alert.deltaValue]]"
                            unit="[[alert.deltaUnit]]">
                        </scalar-span>
                      </td>

                      <td>
                        <scalar-span
                            value="[[alert.percentDeltaValue]]"
                            unit="[[alert.percentDeltaUnit]]"
                            maximum-fraction-digits="1">
                        </scalar-span>
                      </td>
                    </tr>
                  </template>
                </template>
              </tbody>
            </template>
          </table>
        </div>
      </template>
    `;
  }

  ready() {
    super.ready();
    this.scrollIntoView(true);
  }

  anySelectedAlerts_(alertGroups) {
    return AlertsTable.getSelectedAlerts(alertGroups).length > 0;
  }

  selectedCount_(alertGroup) {
    if (!alertGroup) return '';
    if (alertGroup.alerts.length === 1) return '';
    let count = 0;
    for (const alert of alertGroup.alerts) {
      if (alert.isSelected) ++count;
    }
    if (count === 0) return '';
    return `${count}/${alertGroup.alerts.length}`;
  }

  allTriaged_(alertGroups, showingTriaged) {
    if (showingTriaged) return alertGroups.length === 0;
    return (alertGroups || []).filter(group =>
      group.alerts.length > group.triaged.count).length === 0;
  }

  alertRevisionString_(alert) {
    if (alert.startRevision === alert.endRevision) return alert.startRevision;
    return alert.startRevision + '-' + alert.endRevision;
  }

  alertRevisionHref_(alert) {
    // Most monitored timeseries on ChromiumPerf bots use revisions that are
    // supported by test-results.appspot.com.
    // TODO(benjhayden) Support revision range links more generally.
    if (alert.master === 'ChromiumPerf') return `http://test-results.appspot.com/revision_range?start=${alert.startRevision}&end=${alert.endRevision}&n=1000`;
    return '';
  }

  breakWords_(str) {
    return breakWords(str);
  }

  isExpandedGroup_(groupIsExpanded, triagedIsExpanded) {
    return groupIsExpanded || triagedIsExpanded;
  }

  shouldDisplayAlert_(
      areAlertGroupsPlaceholders, showingTriaged, alertGroup, alertIndex,
      triagedExpanded) {
    return AlertsTable.shouldDisplayAlert(
        areAlertGroupsPlaceholders, showingTriaged, alertGroup, alertIndex,
        triagedExpanded);
  }

  shouldDisplayExpandGroupButton_(
      alertGroup, alertIndex, showingTriaged, sortColumn, sortDescending) {
    return AlertsTable.shouldDisplayExpandGroupButton(
        alertGroup, alertIndex, showingTriaged);
  }

  getExpandGroupButtonLabel_(alertGroup, showingTriaged) {
    if (showingTriaged) return alertGroup.alerts.length;
    return alertGroup.alerts.length - alertGroup.triaged.count;
  }

  shouldDisplayExpandTriagedButton_(
      showingTriaged, alertGroup, alertIndex, sortColumn, sortDescending) {
    return AlertsTable.shouldDisplayExpandTriagedButton(
        showingTriaged, alertGroup, alertIndex);
  }

  shouldDisplaySelectedCount_(
      showingTriaged, alertGroup, alertIndex, sortColumn, sortDescending) {
    if (showingTriaged) return alertIndex === 0;
    return alertIndex === alertGroup.alerts.findIndex(a => !a.bugId);
  }

  isAlertIgnored_(bugId) {
    return bugId < 0;
  }

  arePlaceholders_(alertGroups) {
    return alertGroups === AlertsTable.PLACEHOLDER_ALERT_GROUPS;
  }

  async onSelectAll_(event) {
    event.target.checked = !event.target.checked;
    await this.dispatch('selectAllAlerts', this.statePath);
    this.dispatchEvent(new CustomEvent('selected', {
      bubbles: true,
      composed: true,
    }));
  }

  async onSelect_(event) {
    let shiftKey = false;
    if (event.detail && event.detail.event &&
        (event.detail.event.shiftKey ||
          (event.detail.event.detail && event.detail.event.detail.shiftKey))) {
      shiftKey = true;
    }
    await this.dispatch('selectAlert', this.statePath,
        event.model.parentModel.alertGroupIndex,
        event.model.alertIndex,
        shiftKey);
    this.dispatchEvent(new CustomEvent('selected', {
      bubbles: true,
      composed: true,
    }));
  }

  async onSort_(event) {
    await this.dispatch('sort', this.statePath, event.target.name);
    this.dispatchEvent(new CustomEvent('sort', {
      bubbles: true,
      composed: true,
    }));
  }

  async onRowClick_(event) {
    if (event.target.tagName !== 'TD') return;
    this.dispatchEvent(new CustomEvent('alert-click', {
      bubbles: true,
      composed: true,
      detail: {
        alertGroupIndex: event.model.alertGroupIndex,
        alertIndex: event.model.alertIndex,
      },
    }));
  }
}

AlertsTable.getSelectedAlerts = alertGroups => {
  const selectedAlerts = [];
  for (const alertGroup of alertGroups) {
    for (const alert of alertGroup.alerts) {
      if (alert.isSelected) {
        selectedAlerts.push(alert);
      }
    }
  }
  return selectedAlerts;
};

AlertsTable.shouldDisplayAlert = (
    areAlertGroupsPlaceholders, showingTriaged, alertGroup, alertIndex,
    triagedExpanded) => {
  if (areAlertGroupsPlaceholders) return true;
  if (showingTriaged) return alertGroup.isExpanded || (alertIndex === 0);

  if (!alertGroup.alerts[alertIndex]) return false;
  const isTriaged = alertGroup.alerts[alertIndex].bugId;
  const firstUntriagedIndex = alertGroup.alerts.findIndex(a => !a.bugId);
  if (alertGroup.isExpanded) {
    return !isTriaged || triagedExpanded || (
      alertIndex === firstUntriagedIndex);
  }
  if (isTriaged) return triagedExpanded;
  return alertIndex === firstUntriagedIndex;
};

AlertsTable.shouldDisplayExpandGroupButton = (
    alertGroup, alertIndex, showingTriaged) => {
  if (showingTriaged) {
    return (alertIndex === 0) && alertGroup.alerts.length > 1;
  }
  return (alertIndex === alertGroup.alerts.findIndex(a => !a.bugId)) && (
    alertGroup.alerts.length > (1 + alertGroup.triaged.count));
};

AlertsTable.shouldDisplayExpandTriagedButton = (
    showingTriaged, alertGroup, alertIndex) => {
  if (showingTriaged || (alertGroup.triaged.count === 0)) return false;
  return alertIndex === alertGroup.alerts.findIndex(a => !a.bugId);
};

AlertsTable.compareAlerts = (alertA, alertB, sortColumn) => {
  let valueA = alertA[sortColumn];
  let valueB = alertB[sortColumn];
  if (sortColumn === 'percentDeltaValue') {
    valueA = Math.abs(valueA);
    valueB = Math.abs(valueB);
  }
  if (typeof valueA === 'string') return valueA.localeCompare(valueB);
  return valueA - valueB;
};

AlertsTable.sortGroups = (
    alertGroups, sortColumn, sortDescending, showingTriaged) => {
  const factor = sortDescending ? -1 : 1;
  if (sortColumn === 'count') {
    alertGroups = [...alertGroups];
    // See AlertsTable.getExpandGroupButtonLabel_.
    if (showingTriaged) {
      alertGroups.sort((groupA, groupB) =>
        factor * (groupA.alerts.length - groupB.alerts.length));
    } else {
      alertGroups.sort((groupA, groupB) =>
        factor * ((groupA.alerts.length - groupA.triaged.count) -
          (groupB.alerts.length - groupB.triaged.count)));
    }
  } else if (sortColumn === 'triaged') {
    alertGroups = [...alertGroups];
    alertGroups.sort((groupA, groupB) =>
      factor * (groupA.triaged.count - groupB.triaged.count));
  } else {
    alertGroups = alertGroups.map(group => {
      const alerts = Array.from(group.alerts);
      alerts.sort((alertA, alertB) => factor * AlertsTable.compareAlerts(
          alertA, alertB, sortColumn));
      return {
        ...group,
        alerts,
      };
    });
    alertGroups.sort((groupA, groupB) => factor * AlertsTable.compareAlerts(
        groupA.alerts[0], groupB.alerts[0], sortColumn));
  }
  return alertGroups;
};

AlertsTable.PLACEHOLDER_ALERT_GROUPS = [];
AlertsTable.DASHES = '-'.repeat(5);
for (let i = 0; i < 5; ++i) {
  AlertsTable.PLACEHOLDER_ALERT_GROUPS.push({
    isSelected: false,
    triaged: {
      count: 0,
      isExpanded: false,
    },
    alerts: [
      {
        bugId: AlertsTable.DASHES,
        startRevision: AlertsTable.DASHES,
        endRevision: AlertsTable.DASHES,
        suite: AlertsTable.DASHES,
        measurement: AlertsTable.DASHES,
        master: AlertsTable.DASHES,
        bot: AlertsTable.DASHES,
        case: AlertsTable.DASHES,
        deltaValue: 0,
        deltaUnit: tr.b.Unit.byName.countDelta_biggerIsBetter,
        percentDeltaValue: 0,
        percentDeltaUnit:
          tr.b.Unit.byName.normalizedPercentageDelta_biggerIsBetter,
      },
    ],
  });
}

AlertsTable.State = {
  previousSelectedAlertKey: options => undefined,
  alertGroups: options => options.alertGroups ||
    AlertsTable.PLACEHOLDER_ALERT_GROUPS,
  selectedAlertsCount: options => 0,
  showBugColumn: options => options.showBugColumn !== false,
  showMasterColumn: options => options.showMasterColumn !== false,
  showCaseColumn: options => options.showCaseColumn !== false,
  showTriagedColumn: options => options.showTriagedColumn !== false,
  showingTriaged: options => options.showingTriaged || false,
  sortColumn: options => options.sortColumn || 'startRevision',
  sortDescending: options => options.sortDescending || false,
};

AlertsTable.properties = buildProperties('state', AlertsTable.State);
AlertsTable.buildState = options => buildState(AlertsTable.State, options);

AlertsTable.properties.areAlertGroupsPlaceholders = {
  computed: 'arePlaceholders_(alertGroups)',
};

AlertsTable.actions = {
  selectAllAlerts: statePath => async(dispatch, getState) => {
    dispatch({
      type: AlertsTable.reducers.selectAllAlerts.name,
      statePath,
    });
  },

  selectAlert: (statePath, alertGroupIndex, alertIndex, shiftKey) =>
    async(dispatch, getState) => {
      dispatch({
        type: AlertsTable.reducers.selectAlert.name,
        statePath,
        alertGroupIndex,
        alertIndex,
        shiftKey,
      });
    },

  sort: (statePath, sortColumn) => async(dispatch, getState) => {
    dispatch({
      type: AlertsTable.reducers.sort.name,
      statePath,
      sortColumn,
    });
  },
};

AlertsTable.reducers = {
  sort: (state, action, rootState) => {
    if (state.alertGroups === AlertsTable.PLACEHOLDER_ALERT_GROUPS) {
      return state;
    }
    const sortDescending = state.sortDescending ^ (state.sortColumn ===
        action.sortColumn);
    const alertGroups = AlertsTable.sortGroups(
        state.alertGroups, action.sortColumn, sortDescending);
    return {
      ...state,
      sortColumn: action.sortColumn,
      sortDescending,
      alertGroups,
    };
  },

  selectAlert: (state, action, rootState) => {
    let alertGroups = state.alertGroups;
    const alertGroup = alertGroups[action.alertGroupIndex];
    let alerts = alertGroup.alerts;
    const alert = alerts[action.alertIndex];
    const isSelected = !alert.isSelected;

    if (action.shiftKey) {
      // [De]select all alerts between previous selected alert and |alert|.
      // Deep-copy alerts so that we can freely modify them.
      // Copy references to individual alerts out of their groups to reflect
      // the flat list of checkboxes that the user sees.
      const flatList = [];
      alertGroups = alertGroups.map(g => {
        return {
          ...g,
          alerts: g.alerts.map(a => {
            const clone = {...a};
            flatList.push(clone);
            return clone;
          }),
        };
      });
      // Find the indices of the previous selected alert and |alert| in
      // flatList.
      const indices = new tr.b.math.Range();
      const keys = [state.previousSelectedAlertKey, alert.key];
      for (let i = 0; i < flatList.length; ++i) {
        if (keys.includes(flatList[i].key)) indices.addValue(i);
      }
      if (state.previousSelectedAlertKey === undefined) indices.addValue(0);
      // Set isSelected for all alerts that appear in the table between the
      // previous selected alert and |alert|.
      for (let i = indices.min; i <= indices.max; ++i) {
        flatList[i].isSelected = isSelected;
      }
    } else {
      let toggleAll = false;
      if (!alertGroup.isExpanded) {
        if (state.showingTriaged) {
          toggleAll = action.alertIndex === 0;
        } else {
          toggleAll = action.alertIndex === alertGroup.alerts.findIndex(
              a => !a.bugId);
        }
      }
      if (toggleAll) {
        alerts = alerts.map(alert => {
          if (!state.showingTriaged && alert.bugId) return alert;
          return {
            ...alert,
            isSelected,
          };
        });
      } else {
        // Only toggle this alert.
        alerts = setImmutable(
            alerts, `${action.alertIndex}.isSelected`, isSelected);
      }

      alertGroups = setImmutable(
          state.alertGroups, `${action.alertGroupIndex}.alerts`, alerts);
    }

    const selectedAlertsCount = AlertsTable.getSelectedAlerts(
        alertGroups).length;
    return {
      ...state,
      alertGroups,
      previousSelectedAlertKey: alert.key,
      selectedAlertsCount,
    };
  },

  selectAllAlerts: (state, action, rootState) => {
    const select = (state.selectedAlertsCount === 0);
    const alertGroups = state.alertGroups.map(alertGroup => {
      return {
        ...alertGroup,
        alerts: alertGroup.alerts.map(alert => {
          return {
            ...alert,
            isSelected: select,
          };
        }),
      };
    });
    return {
      ...state,
      alertGroups,
      selectedAlertsCount: AlertsTable.getSelectedAlerts(alertGroups).length,
    };
  },
};

ElementBase.register(AlertsTable);
