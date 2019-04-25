/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './cp-checkbox.js';
import './cp-input.js';
import './cp-switch.js';
import './raised-button.js';
import './recommended-options.js';
import '/@polymer/polymer/lib/elements/dom-if.js';
import '/@polymer/polymer/lib/elements/dom-repeat.js';
import * as PolymerAsync from '/@polymer/polymer/lib/utils/async.js';
import AlertsTable from './alerts-table.js';
import ElementBase from './element-base.js';
import MenuInput from './menu-input.js';
import OptionGroup from './option-group.js';
import ReportNamesRequest from './report-names-request.js';
import SheriffsRequest from './sheriffs-request.js';
import {TOGGLE, UPDATE} from './simple-redux.js';
import {get} from '/@polymer/polymer/lib/utils/path.js';
import {html} from '/@polymer/polymer/polymer-element.js';

import {
  buildState,
  buildProperties,
} from './utils.js';

export default class AlertsControls extends ElementBase {
  static get is() { return 'alerts-controls'; }

  static get template() {
    return html`
      <style>
        :host {
          align-items: center;
          display: flex;
          margin-bottom: 8px;
        }

        #sheriff-container,
        #bug-container,
        #report-container,
        #report,
        #min-revision {
          margin-right: 8px;
        }

        #report-container {
          display: flex;
        }

        #triaged {
          margin-left: 8px;
          margin-right: 8px;
        }

        #spacer {
          flex-grow: 1;
        }

        #recent-bugs-container {
          position: relative;
        }

        .bug_notification {
          background-color: var(--background-color, white);
          box-shadow: var(--elevation-2);
          overflow: hidden;
          padding: 8px;
          position: absolute;
          right: 0;
          white-space: nowrap;
          z-index: var(--layer-menu, 100);
        }

        #recent-bugs-table {
          margin: 0;
          padding: 0;
        }

        #filter[enabled] {
          background-color: var(--primary-color-dark, blue);
          border-radius: 50%;
          color: var(--background-color, white);
          padding: 4px;
        }

        iron-icon {
          cursor: pointer;
          flex-shrink: 0;
          height: var(--icon-size, 1em);
          width: var(--icon-size, 1em);
        }

        #close {
          align-self: flex-start;
        }

        #edit, #documentation {
          color: var(--primary-color-dark, blue);
          padding: 8px;
        }
      </style>

      <chops-signin-aware on-user-update="onUserUpdate_">
      </chops-signin-aware>

      <iron-collapse
          horizontal
          id="sheriff-container"
          opened="[[showMenuInput_(showEmptyInputs, sheriff, bug, report,
                                    minRevision, maxRevision)]]">
        <menu-input
            id="sheriff"
            state-path="[[statePath]].sheriff"
            on-clear="onSheriffClear_"
            on-option-select="onSheriffSelect_">
          <recommended-options slot="top" state-path="[[statePath]].sheriff">
          </recommended-options>
        </menu-input>
      </iron-collapse>

      <iron-collapse
          horizontal
          id="bug-container"
          opened="[[showMenuInput_(showEmptyInputs, bug, sheriff, report,
                                    minRevision, maxRevision)]]">
        <menu-input
            id="bug"
            state-path="[[statePath]].bug"
            on-clear="onBugClear_"
            on-input-keyup="onBugKeyup_"
            on-option-select="onBugSelect_">
          <recommended-options slot="top" state-path="[[statePath]].bug">
          </recommended-options>
        </menu-input>
      </iron-collapse>

      <iron-collapse
          horizontal
          id="report-container"
          opened="[[showMenuInput_(showEmptyInputs, report, sheriff, bug,
                                    minRevision, maxRevision)]]">
        <menu-input
            id="report"
            state-path="[[statePath]].report"
            on-clear="onReportClear_"
            on-option-select="onReportSelect_">
          <recommended-options slot="top" state-path="[[statePath]].report">
          </recommended-options>
        </menu-input>
      </iron-collapse>

      <iron-collapse
          horizontal
          id="sheriff-container"
          opened="[[showInput_(showEmptyInputs, minRevision, maxRevision,
                                sheriff, bug, report)]]">
        <cp-input
            id="min-revision"
            value="[[minRevision]]"
            label="Min Revision"
            on-keyup="onMinRevisionKeyup_">
        </cp-input>
      </iron-collapse>

      <iron-collapse
          horizontal
          id="sheriff-container"
          opened="[[showInput_(showEmptyInputs, minRevision, maxRevision,
                                sheriff, bug, report)]]">
        <cp-input
            id="max-revision"
            value="[[maxRevision]]"
            label="Max Revision"
            on-keyup="onMaxRevisionKeyup_">
        </cp-input>
      </iron-collapse>

      <iron-icon
          id="filter"
          icon="cp:filter"
          enabled$="[[showEmptyInputs]]"
          on-click="onFilter_">
      </iron-icon>

      <cp-switch
          id="improvements"
          disabled="[[!isEmpty_(bug.selectedOptions)]]"
          checked$="[[showingImprovements]]"
          on-change="onToggleImprovements_">
        <template is="dom-if" if="[[showingImprovements]]">
          Regressions and Improvements
        </template>
        <template is="dom-if" if="[[!showingImprovements]]">
          Regressions Only
        </template>
      </cp-switch>

      <cp-switch
          id="triaged"
          disabled="[[!isEmpty_(bug.selectedOptions)]]"
          checked$="[[showingTriaged]]"
          on-change="onToggleTriaged_">
        <template is="dom-if" if="[[showingTriaged]]">
          New and Triaged
        </template>
        <template is="dom-if" if="[[!showingTriaged]]">
          New Only
        </template>
      </cp-switch>

      <span id=spacer></span>

      <span id="recent-bugs-container">
        <raised-button
            id="recent-bugs"
            disabled$="[[isEmpty_(recentlyModifiedBugs)]]"
            on-click="onClickRecentlyModifiedBugs_">
          Recent Bugs
        </raised-button>

        <iron-collapse
            class="bug_notification"
            opened="[[hasTriagedNew]]">
          Created
          <a href="[[crbug_(triagedBugId)]]" target="_blank">
            [[triagedBugId]]
          </a>
        </iron-collapse>

        <iron-collapse
            class="bug_notification"
            opened="[[hasTriagedExisting]]">
          Updated
          <a href="[[crbug_(triagedBugId)]]" target="_blank">
            [[triagedBugId]]
          </a>
        </iron-collapse>

        <iron-collapse
            class="bug_notification"
            opened="[[hasIgnored]]">
          Ignored [[ignoredCount]] alert[[plural_(ignoredCount)]]
        </iron-collapse>

        <iron-collapse
            class="bug_notification"
            opened="[[showingRecentlyModifiedBugs]]"
            on-blur="onRecentlyModifiedBugsBlur_">
          <table id="recent-bugs-table">
            <thead>
              <tr>
                <th>Bug #</th>
                <th>Summary</th>
              </tr>
            </thead>
            <template is="dom-repeat" items="[[recentlyModifiedBugs]]"
                                      as="bug">
              <tr>
                <td>
                  <a href="[[crbug_(bug.id)]]" target="_blank">
                    [[bug.id]]
                  </a>
                </td>
                <td>[[bug.summary]]</td>
              </tr>
            </template>
          </table>
        </iron-collapse>
      </span>

      <iron-icon id="close" icon="cp:close" on-click="onClose_">
      </iron-icon>
    `;
  }

  connectedCallback() {
    super.connectedCallback();
    this.dispatch('connected', this.statePath);

    this.dispatchSources_();
  }

  async onUserUpdate_() {
    await this.dispatch('loadReportNames', this.statePath);
    await this.dispatch('loadSheriffs', this.statePath);
  }

  async onFilter_() {
    await this.dispatch(TOGGLE(this.statePath + '.showEmptyInputs'));
  }

  showMenuInput_(showEmptyInputs, thisInput, thatInput, otherInput,
      minRevision, maxRevision) {
    if (showEmptyInputs) return true;
    if (thisInput && thisInput.selectedOptions.length) return true;
    if (!thatInput || !otherInput) return true;
    if (thatInput.selectedOptions.length === 0 &&
        otherInput.selectedOptions.length === 0 &&
        !minRevision && !maxRevision) {
      // Show all inputs when they're all empty.
      return true;
    }
    return false;
  }

  showInput_(showEmptyInputs, thisInput, thatInput, menuA, menuB, menuC) {
    if (showEmptyInputs) return true;
    if (thisInput) return true;
    if (!menuA || !menuB || !menuC) return true;
    if (menuA.selectedOptions.length === 0 &&
        menuB.selectedOptions.length === 0 &&
        menuC.selectedOptions.length === 0 &&
        !thatInput) {
      // Show all inputs when they're all empty.
      return true;
    }
    return false;
  }

  arePlaceholders_(alertGroups) {
    return alertGroups === AlertsTable.placeholderAlertGroups();
  }

  crbug_(bugId) {
    return `http://crbug.com/${bugId}`;
  }

  async dispatchSources_() {
    if (!this.sheriff || !this.bug || !this.report) return;
    const sources = await AlertsControls.compileSources(
        this.sheriff.selectedOptions,
        this.bug.selectedOptions,
        this.report.selectedOptions,
        this.minRevision, this.maxRevision,
        this.showingImprovements, this.showingTriaged);
    this.dispatchEvent(new CustomEvent('sources', {
      bubbles: true,
      composed: true,
      detail: {sources},
    }));
  }

  async onSheriffClear_(event) {
    this.dispatch(MenuInput.actions.focus(this.statePath + '.sheriff'));
    this.dispatchSources_();
  }

  async onSheriffSelect_(event) {
    this.dispatchSources_();
  }

  async onBugClear_(event) {
    this.dispatch(MenuInput.actions.focus(this.statePath + '.bug'));
    this.dispatchSources_();
  }

  async onBugKeyup_(event) {
    await this.dispatch('onBugKeyup', this.statePath, event.detail.value);
  }

  async onBugSelect_(event) {
    await this.dispatch(UPDATE(this.statePath, {
      showingTriaged: true,
      showingImprovements: true,
    }));
    this.dispatchSources_();
  }

  async onReportClear_(event) {
    this.dispatch(MenuInput.actions.focus(this.statePath + '.report'));
    this.dispatchSources_();
  }

  async onReportSelect_(event) {
    this.dispatchSources_();
  }

  async onMinRevisionKeyup_(event) {
    await this.dispatch(UPDATE(this.statePath, {
      minRevision: event.target.value,
    }));
    this.debounce('dispatchSources', () => {
      this.dispatchSources_();
    }, PolymerAsync.timeOut.after(AlertsControls.TYPING_DEBOUNCE_MS));
  }

  async onMaxRevisionKeyup_(event) {
    await this.dispatch(UPDATE(this.statePath, {
      maxRevision: event.target.value,
    }));
    this.debounce('dispatchSources', () => {
      this.dispatchSources_();
    }, PolymerAsync.timeOut.after(AlertsControls.TYPING_DEBOUNCE_MS));
  }

  async onToggleImprovements_(event) {
    this.dispatch(TOGGLE(this.statePath + '.showingImprovements'));
    this.dispatchSources_();
  }

  async onToggleTriaged_(event) {
    this.dispatch(TOGGLE(this.statePath + '.showingTriaged'));
  }

  async onClickRecentlyModifiedBugs_(event) {
    await this.dispatch('toggleRecentlyModifiedBugs', this.statePath);
  }

  async onRecentlyModifiedBugsBlur_(event) {
    await this.dispatch('toggleRecentlyModifiedBugs', this.statePath);
  }

  async onClose_(event) {
    this.dispatchEvent(new CustomEvent('close-section', {
      bubbles: true,
      composed: true,
      detail: {sectionId: this.sectionId},
    }));
  }

  observeTriaged_() {
    if (this.hasTriagedNew || this.hasTriagedExisting || this.hasIgnored) {
      this.$['recent-bugs'].scrollIntoView(true);
    }
  }

  observeRecentPerformanceBugs_() {
    this.dispatch('observeRecentPerformanceBugs', this.statePath);
  }
}

AlertsControls.TYPING_DEBOUNCE_MS = 300;

AlertsControls.State = {
  bug: options => MenuInput.buildState({
    label: 'Bug',
    options: [],
    selectedOptions: options.bugs,
  }),
  hasTriagedNew: options => false,
  hasTriagedExisting: options => false,
  hasIgnored: options => false,
  ignoredCount: options => 0,
  maxRevision: options => options.maxRevision || '',
  minRevision: options => options.minRevision || '',
  recentlyModifiedBugs: options => [],
  report: options => MenuInput.buildState({
    label: 'Report',
    options: [],
    selectedOptions: options.reports || [],
  }),
  sheriff: options => MenuInput.buildState({
    label: 'Sheriff',
    options: [],
    selectedOptions: options.sheriffs || [],
  }),
  showEmptyInputs: options => options.showEmptyInputs || false,
  showingTriaged: options => options.showingTriaged || false,
  showingImprovements: options => options.showingImprovements || false,
  showingRecentlyModifiedBugs: options => false,
  triagedBugId: options => 0,
  alertGroups: options => options.alertGroups ||
    AlertsTable.placeholderAlertGroups(),
};

AlertsControls.observers = [
  'observeTriaged_(hasIgnored, hasTriagedExisting, hasTriagedNew)',
  'observeRecentPerformanceBugs_(recentPerformanceBugs)',
];

AlertsControls.buildState = options =>
  buildState(AlertsControls.State, options);

AlertsControls.properties = {
  ...buildProperties('state', AlertsControls.State),
  recentPerformanceBugs: {statePath: 'recentPerformanceBugs'},
};

AlertsControls.properties.areAlertGroupsPlaceholders = {
  computed: 'arePlaceholders_(alertGroups)',
};

AlertsControls.actions = {
  toggleRecentlyModifiedBugs: statePath => async(dispatch, getState) => {
    dispatch(TOGGLE(`${statePath}.showingRecentlyModifiedBugs`));
  },

  onBugKeyup: (statePath, bugId) => async(dispatch, getState) => {
    dispatch({
      type: AlertsControls.reducers.onBugKeyup.name,
      statePath,
      bugId,
    });
  },

  loadReportNames: statePath => async(dispatch, getState) => {
    const reportTemplateInfos = await new ReportNamesRequest().response;
    const reportNames = reportTemplateInfos.map(t => t.name);
    dispatch(UPDATE(statePath + '.report', {
      options: OptionGroup.groupValues(reportNames),
      label: `Reports (${reportNames.length})`,
    }));
  },

  loadSheriffs: statePath => async(dispatch, getState) => {
    const sheriffs = await new SheriffsRequest().response;
    dispatch({
      type: AlertsControls.reducers.receiveSheriffs.name,
      statePath,
      sheriffs,
    });

    const state = get(getState(), statePath);
    if (state.sheriff.selectedOptions.length === 0) {
      dispatch(MenuInput.actions.focus(statePath + '.sheriff'));
    }
  },

  connected: statePath => async(dispatch, getState) => {
    AlertsControls.actions.loadReportNames(statePath)(dispatch, getState);
    AlertsControls.actions.loadSheriffs(statePath)(dispatch, getState);
    dispatch({
      type: AlertsControls.reducers.receiveRecentlyModifiedBugs.name,
      statePath,
      json: localStorage.getItem('recentlyModifiedBugs'),
    });
  },

  observeRecentPerformanceBugs: statePath => async(dispatch, getState) => {
    dispatch({
      type: AlertsControls.reducers.receiveRecentPerformanceBugs.name,
      statePath,
    });
  },
};

AlertsControls.reducers = {
  receiveSheriffs: (state, {sheriffs}, rootState) => {
    const sheriff = MenuInput.buildState({
      label: `Sheriffs (${sheriffs.length})`,
      options: sheriffs,
      selectedOptions: state.sheriff ? state.sheriff.selectedOptions : [],
    });
    return {...state, sheriff};
  },

  onBugKeyup: (state, action, rootState) => {
    const options = state.bug.options.filter(option => !option.manual);
    const bugIds = options.map(option => option.value);
    if (action.bugId.match(/^\d+$/) &&
        !bugIds.includes(action.bugId)) {
      options.unshift({
        value: action.bugId,
        label: action.bugId,
        manual: true,
      });
    }
    return {
      ...state,
      bug: {
        ...state.bug,
        options,
      },
    };
  },

  receiveRecentPerformanceBugs: (state, action, rootState) => {
    const options = rootState.recentPerformanceBugs.map(bug => {
      return {
        label: bug.id + ' ' + bug.summary,
        value: bug.id,
      };
    });
    return {...state, bug: {...state.bug, options}};
  },

  receiveRecentlyModifiedBugs: (state, {json}, rootState) => {
    if (!json) return state;
    return {...state, recentlyModifiedBugs: JSON.parse(json)};
  },
};

function maybeInt(x) {
  x = parseInt(x);
  return isNaN(x) ? undefined : x;
}

// Maximum number of alerts to count (not return) when fetching alerts for a
// sheriff rotation. When non-zero, /api/alerts returns the number of alerts
// that would match the datastore query (up to COUNT_LIMIT) as response.count.
// The maximum number of alerts to return from /api/alerts is given by `limit`
// in AlertsRequest.
// See count_limit in Anomaly.QueryAsync() and totalCount in AlertsSection.
const COUNT_LIMIT = 5000;

AlertsControls.compileSources = async(
  sheriffs, bugs, reports, minRevision, maxRevision, improvements,
  showingTriaged) => {
  // Returns a list of AlertsRequest bodies. See ../api/alerts.py for
  // request body parameters.
  const revisions = {};
  minRevision = maybeInt(minRevision);
  maxRevision = maybeInt(maxRevision);
  if (minRevision !== undefined) revisions.min_end_revision = minRevision;
  if (maxRevision !== undefined) revisions.max_start_revision = maxRevision;
  const sources = [];
  for (const sheriff of sheriffs) {
    const source = {sheriff, recovered: false, ...revisions};
    source.count_limit = COUNT_LIMIT;
    source.is_improvement = improvements;
    if (!showingTriaged) source.bug_id = '';
    sources.push(source);
  }
  for (const bug of bugs) {
    sources.push({bug_id: bug, ...revisions});
  }
  if (reports.length) {
    const reportTemplateInfos = await new ReportNamesRequest().response;
    for (const name of reports) {
      for (const reportId of reportTemplateInfos) {
        if (reportId.name === name) {
          sources.push({report: reportId.id, ...revisions});
          break;
        }
      }
    }
  }
  if (sources.length === 0 && (minRevision || maxRevision)) {
    sources.push(revisions);
  }
  return sources;
};

ElementBase.register(AlertsControls);
