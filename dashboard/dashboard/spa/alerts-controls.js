/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './cp-icon.js';
import './recommended-options.js';
import '@chopsui/chops-button';
import '@chopsui/chops-checkbox';
import '@chopsui/chops-input';
import '@chopsui/chops-switch';
import * as PolymerAsync from '@polymer/polymer/lib/utils/async.js';
import AlertsTable from './alerts-table.js';
import MenuInput from './menu-input.js';
import OptionGroup from './option-group.js';
import ReportNamesRequest from './report-names-request.js';
import SheriffsRequest from './sheriffs-request.js';
import {ElementBase, STORE} from './element-base.js';
import {TOGGLE, UPDATE} from './simple-redux.js';
import {crbug, plural} from './utils.js';
import {get} from 'dot-prop-immutable';
import {html, css} from 'lit-element';

export default class AlertsControls extends ElementBase {
  static get is() { return 'alerts-controls'; }

  static get properties() {
    return {
      recentPerformanceBugs: Array,
      areAlertGroupsPlaceholders: Boolean,
      userEmail: String,

      statePath: String,
      errors: Array,
      bug: Object,
      hasTriagedNew: Boolean,
      hasTriagedExisting: Boolean,
      hasIgnored: Boolean,
      ignoredCount: Number,
      maxRevision: String,
      minRevision: String,
      recentlyModifiedBugs: Array,
      report: Object,
      sheriff: Object,
      showEmptyInputs: Boolean,
      showingTriaged: Boolean,
      showingImprovements: Boolean,
      showingRecentlyModifiedBugs: Boolean,
      triagedBugId: Number,
      alertGroups: Array,
      isHelping: Boolean,
    };
  }

  static buildState(options = {}) {
    return {
      errors: [],
      bug: MenuInput.buildState({
        label: 'Bug',
        options: [],
        selectedOptions: options.bugs,
      }),
      hasTriagedNew: false,
      hasTriagedExisting: false,
      hasIgnored: false,
      ignoredCount: 0,
      maxRevision: options.maxRevision || '',
      minRevision: options.minRevision || '',
      recentlyModifiedBugs: [],
      report: MenuInput.buildState({
        label: 'Report',
        options: [],
        selectedOptions: options.reports || [],
      }),
      sheriff: MenuInput.buildState({
        label: 'Sheriff',
        options: [],
        selectedOptions: options.sheriffs || [],
      }),
      showEmptyInputs: options.showEmptyInputs || false,
      showingTriaged: options.showingTriaged || false,
      showingImprovements: options.showingImprovements || false,
      showingRecentlyModifiedBugs: false,
      triagedBugId: 0,
      alertGroups: options.alertGroups ||
        AlertsTable.placeholderAlertGroups(),
      isHelping: false,
    };
  }

  static get styles() {
    return css`
      :host {
        align-items: center;
        display: flex;
        margin-bottom: 8px;
      }

      #sheriff-container,
      #bug-container,
      #report-container {
        margin-right: 8px;
      }

      chops-input {
        margin-right: 8px;
        margin-top: 12px;
      }

      #report-container {
        display: flex;
      }
      #report-container[hidden] {
        display: none;
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

      cp-icon {
        cursor: pointer;
        flex-shrink: 0;
      }

      #help-container {
        align-self: flex-start;
        position: relative;
      }
      #help {
        color: var(--primary-color-dark, blue);
      }
      #help-dialog {
        background: var(--background-color, white);
        box-shadow: var(--elevation-2);
        display: none;
        padding: 16px;
        position: absolute;
        right: 0;
        width: 25em;
        z-index: var(--layer-menu, 100);
      }
      #help-dialog[isopen] {
        display: block;
      }

      #close {
        align-self: flex-start;
      }
    `;
  }

  render() {
    const showSheriff = this.showMenuInput_(
        this.showEmptyInputs, this.sheriff, this.bug, this.report,
        this.minRevision, this.maxRevision);
    const showBug = this.showMenuInput_(
        this.showEmptyInputs, this.bug, this.sheriff, this.report,
        this.minRevision, this.maxRevision);
    const showReport = this.showMenuInput_(
        this.showEmptyInputs, this.report, this.sheriff, this.bug,
        this.minRevision, this.maxRevision);
    const showMin = this.showInput_(
        this.showEmptyInputs, this.minRevision, this.maxRevision, this.sheriff,
        this.bug, this.report);
    const showMax = this.showInput_(
        this.showEmptyInputs, this.minRevision, this.maxRevision, this.sheriff,
        this.bug, this.report);

    const improvementsTooltip = this.showingImprovements ?
      'Now showing both regressions and improvements. Click to toggle to ' +
      'show only regressions.' :
      'Now showing regressions but not improvements. Click to toggle to ' +
      'show both regressions and improvements.';

    const triagedTooltip = this.showingTriaged ?
      'Now showing both triaged and untriaged alerts. Click to toggle to ' +
      'show only untriaged alerts.' :
      'Now showing only untriaged alerts. Click to toggle to show both ' +
      'triaged and untriaged alerts.';

    return html`
      <div id="sheriff-container"
          ?hidden="${!showSheriff}">
        <menu-input
            id="sheriff"
            .statePath="${this.statePath}.sheriff"
            @clear="${this.onSheriffClear_}"
            @option-select="${this.onSheriffSelect_}">
          <recommended-options
              slot="top"
              .statePath="${this.statePath}.sheriff">
          </recommended-options>
        </menu-input>
      </div>

      <div id="bug-container"
          ?hidden="${!showBug}">
        <menu-input
            id="bug"
            .statePath="${this.statePath}.bug"
            @clear="${this.onBugClear_}"
            @input-keyup="${this.onBugKeyup_}"
            @option-select="${this.onBugSelect_}">
          <recommended-options slot="top" .statePath="${this.statePath}.bug">
          </recommended-options>
        </menu-input>
      </div>

      <div id="report-container"
          ?hidden="${!showReport}">
        <menu-input
            id="report"
            .statePath="${this.statePath}.report"
            @clear="${this.onReportClear_}"
            @option-select="${this.onReportSelect_}">
          <recommended-options
              slot="top"
              .statePath="${this.statePath}.report">
          </recommended-options>
        </menu-input>
      </div>

      <div id="min-container"
          ?hidden="${!showMin}">
        <chops-input
            id="min-revision"
            .value="${this.minRevision}"
            label="Min Revision"
            @keyup="${this.onMinRevisionKeyup_}">
        </chops-input>
      </div>

      <div id="max-container"
          ?hidden="${!showMax}">
        <chops-input
            id="max-revision"
            .value="${this.maxRevision}"
            label="Max Revision"
            @keyup="${this.onMaxRevisionKeyup_}">
        </chops-input>
      </div>

      <cp-icon
          id="filter"
          icon="filter"
          ?enabled="${this.showEmptyInputs}"
          @click="${this.onFilter_}">
      </cp-icon>

      <div ?hidden="${this.bug && this.bug.selectedOptions.length > 0}">
        <chops-switch
            id="improvements"
            title="${improvementsTooltip}"
            ?checked="${this.showingImprovements}"
            @change="${this.onToggleImprovements_}">
          Improvements
        </chops-switch>

        <chops-switch
            id="triaged"
            ?disabled="${this.bug && (this.bug.selectedOptions.length > 0)}"
            title="${triagedTooltip}"
            ?checked="${this.showingTriaged}"
            @change="${this.onToggleTriaged_}">
          Triaged
        </chops-switch>
      </div>

      <span id=spacer></span>

      <span id="recent-bugs-container">
        <chops-button
            id="recent-bugs"
            ?disabled="${
  this.recentlyModifiedBugs && (this.recentlyModifiedBugs.length === 0)}"
            @click="${this.onClickRecentlyModifiedBugs_}">
          Recent Bugs
        </chops-button>

        <div
            class="bug_notification"
            ?hidden="${!this.hasTriagedNew}">
          Created
          <a href="${crbug(this.triagedBugId)}" target="_blank">
            ${this.triagedBugId}
          </a>
        </div>

        <div
            class="bug_notification"
            ?hidden="${!this.hasTriagedExisting}">
          Updated
          <a href="${crbug(this.triagedBugId)}" target="_blank">
            ${this.triagedBugId}
          </a>
        </div>

        <div
            class="bug_notification"
            ?hidden="${!this.hasIgnored}">
          Ignored ${this.ignoredCount} alert${plural(this.ignoredCount)}
        </div>

        <div
            class="bug_notification"
            ?hidden="${!this.showingRecentlyModifiedBugs}"
            tabindex="0"
            @blur="${this.onRecentlyModifiedBugsBlur_}">
          <table id="recent-bugs-table">
            <thead>
              <tr>
                <th>Bug #</th>
                <th>Summary</th>
              </tr>
            </thead>
            ${(this.recentlyModifiedBugs || []).map(bug => html`
              <tr>
                <td>
                  <a href="${crbug(bug.id)}" target="_blank">
                    ${bug.id}
                  </a>
                </td>
                <td>${bug.summary}</td>
              </tr>
            `)}
          </table>
        </div>
      </span>

      <span id="help-container">
        <cp-icon
            id="help"
            tabindex="0"
            icon="help"
            @click="${this.onHelp_}">
        </cp-icon>
        <div
            id="help-dialog"
            tabindex="0"
            ?isopen="${this.isHelping}"
            @keydown="${this.onHelpKeydown_}"
            @blur="${this.onBlurHelp_}">
          When this section is in the middle of the screen, it responds to the
          following hotkeys.
          <table>
            <tr>
              <td>?</td>
              <td>Toggle this dialog</td>
            </tr>
            <tr>
              <td>j</td>
              <td>Move the cursor down through the alerts table</td>
            </tr>
            <tr>
              <td>k</td>
              <td>Move the cursor up through the alerts table</td>
            </tr>
            <tr>
              <td>x</td>
              <td>Toggle selection of the alert at the cursor</td>
            </tr>
            <tr>
              <td>g</td>
              <td>Toggle expansion of the alert group at the cursor</td>
            </tr>
            <tr>
              <td>t</td>
              <td>Toggle expansion of the triaged alerts at the cursor</td>
            </tr>
            <tr>
              <td>a</td>
              <td>Accept autotriage suggestion for selected alerts</td>
            </tr>
            <tr>
              <td>e</td>
              <td>Assign selected alerts to an existing bug</td>
            </tr>
            <tr>
              <td>n</td>
              <td>File a new bug for selected alerts</td>
            </tr>
            <tr>
              <td>i</td>
              <td>Ignore selected alerts</td>
            </tr>
            <tr>
              <td>u</td>
              <td>Unassign selected alerts</td>
            </tr>
            <tr>
              <td>/</td>
              <td>Focus the Sheriff menu</td>
            </tr>
            <tr>
              <td>sc</td>
              <td>Sort the alerts table by Count</td>
            </tr>
            <tr>
              <td>st</td>
              <td>Sort the alerts table by Triaged</td>
            </tr>
            <tr>
              <td>su</td>
              <td>Sort the alerts table by Bug</td>
            </tr>
            <tr>
              <td>sr</td>
              <td>Sort the alertstable by Revision</td>
            </tr>
            <tr>
              <td>ss</td>
              <td>Sort the alerts table by Suite</td>
            </tr>
            <tr>
              <td>sm</td>
              <td>Sort the alerts table by Measurement</td>
            </tr>
            <tr>
              <td>sa</td>
              <td>Sort the alerts table by Master</td>
            </tr>
            <tr>
              <td>sb</td>
              <td>Sort the alerts table by Bot</td>
            </tr>
            <tr>
              <td>se</td>
              <td>Sort the alerts table by Case</td>
            </tr>
            <tr>
              <td>sd</td>
              <td>Sort the alerts table by Delta</td>
            </tr>
            <tr>
              <td>sp</td>
              <td>Sort the alerts table by Percent Delta</td>
            </tr>
          </table>
          For more information, see the
          <a href="https://chromium.googlesource.com/catapult.git/+/HEAD/dashboard/docs/user-guide.md" target="_blank">
            user guide
          </a>.
        </div>
      </span>

      <cp-icon id="close" icon="close" @click="${this.onClose_}"></cp-icon>
    `;
  }

  connectedCallback() {
    super.connectedCallback();
    AlertsControls.connected(this.statePath);
    this.dispatchSources_();
  }

  static async connected(statePath) {
    AlertsControls.loadReportNames(statePath);
    AlertsControls.loadSheriffs(statePath);
    STORE.dispatch({
      type: AlertsControls.reducers.receiveRecentlyModifiedBugs.name,
      statePath,
      json: localStorage.getItem('recentlyModifiedBugs'),
    });
  }

  async stateChanged(rootState) {
    if (!this.statePath) return;

    const oldUserEmail = this.userEmail;
    const oldIsHelping = this.isHelping;
    const oldRecentPerformanceBugs = this.recentPerformanceBugs;

    Object.assign(this, get(rootState, this.statePath));
    this.userEmail = rootState.userEmail;
    this.recentPerformanceBugs = rootState.recentPerformanceBugs;
    this.areAlertGroupsPlaceholders = (this.alertGroups ===
      AlertsTable.placeholderAlertGroups());

    if (this.hasTriagedNew || this.hasTriagedExisting || this.hasIgnored) {
      this.shadowRoot.querySelector('#recent-bugs').scrollIntoView(true);
    }

    if (this.recentPerformanceBugs !== oldRecentPerformanceBugs) {
      STORE.dispatch({
        type: AlertsControls.reducers.receiveRecentPerformanceBugs.name,
        statePath: this.statePath,
      });
    }

    if (this.userEmail !== oldUserEmail) {
      AlertsControls.loadReportNames(this.statePath);
      AlertsControls.loadSheriffs(this.statePath);
    }

    if (this.isHelping && !oldIsHelping) {
      await this.updateComplete;
      this.shadowRoot.querySelector('#help-dialog').focus();
    }
  }

  onHelp_(event) {
    STORE.dispatch(TOGGLE(this.statePath + '.isHelping'));
  }

  onBlurHelp_(event) {
    STORE.dispatch(UPDATE(this.statePath, {isHelping: false}));
  }

  onHelpKeydown_(event) {
    if (event.key === 'Escape') this.onBlurHelp_(event);
  }

  static async loadReportNames(statePath) {
    let infos;
    let error;
    try {
      infos = await new ReportNamesRequest().response;
    } catch (err) {
      error = err;
    }
    STORE.dispatch({
      type: AlertsControls.reducers.receiveReportNames.name,
      statePath, infos, error,
    });
  }

  static async loadSheriffs(statePath) {
    let sheriffs;
    let error;
    try {
      sheriffs = await new SheriffsRequest().response;
    } catch (err) {
      error = err;
    }
    STORE.dispatch({
      type: AlertsControls.reducers.receiveSheriffs.name,
      statePath, sheriffs, error,
    });

    const state = get(STORE.getState(), statePath);
    if (state.sheriff && (state.sheriff.selectedOptions.length === 0)) {
      MenuInput.focus(statePath + '.sheriff');
    }
  }

  async onFilter_() {
    await STORE.dispatch(TOGGLE(this.statePath + '.showEmptyInputs'));
  }

  showMenuInput_(showEmptyInputs, thisInput, thatInput, otherInput,
      minRevision, maxRevision) {
    if (showEmptyInputs) return true;
    if (thisInput && thisInput.selectedOptions &&
        thisInput.selectedOptions.length) {
      return true;
    }
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
    MenuInput.focus(this.statePath + '.sheriff');
    this.dispatchSources_();
  }

  async onSheriffSelect_(event) {
    this.dispatchSources_();
  }

  async onBugClear_(event) {
    MenuInput.focus(this.statePath + '.bug');
    this.dispatchSources_();
  }

  async onBugKeyup_(event) {
    STORE.dispatch({
      type: AlertsControls.reducers.onBugKeyup.name,
      statePath: this.statePath,
      bugId: event.detail.value,
    });
  }

  async onBugSelect_(event) {
    await STORE.dispatch(UPDATE(this.statePath, {
      showingTriaged: true,
      showingImprovements: true,
    }));
    this.dispatchSources_();
  }

  async onReportClear_(event) {
    MenuInput.focus(this.statePath + '.report');
    this.dispatchSources_();
  }

  async onReportSelect_(event) {
    this.dispatchSources_();
  }

  async onMinRevisionKeyup_(event) {
    await STORE.dispatch(UPDATE(this.statePath, {
      minRevision: event.target.value,
    }));
    this.debounce('dispatchSources', () => {
      this.dispatchSources_();
    }, PolymerAsync.timeOut.after(AlertsControls.TYPING_DEBOUNCE_MS));
  }

  async onMaxRevisionKeyup_(event) {
    await STORE.dispatch(UPDATE(this.statePath, {
      maxRevision: event.target.value,
    }));
    this.debounce('dispatchSources', () => {
      this.dispatchSources_();
    }, PolymerAsync.timeOut.after(AlertsControls.TYPING_DEBOUNCE_MS));
  }

  async onToggleImprovements_(event) {
    STORE.dispatch(TOGGLE(this.statePath + '.showingImprovements'));
    this.dispatchSources_();
  }

  async onToggleTriaged_(event) {
    STORE.dispatch(TOGGLE(this.statePath + '.showingTriaged'));
  }

  async onClickRecentlyModifiedBugs_(event) {
    STORE.dispatch(TOGGLE(this.statePath + '.showingRecentlyModifiedBugs'));
  }

  async onRecentlyModifiedBugsBlur_(event) {
    STORE.dispatch(TOGGLE(this.statePath + '.showingRecentlyModifiedBugs'));
  }

  async onClose_(event) {
    this.dispatchEvent(new CustomEvent('close-section', {
      bubbles: true,
      composed: true,
      detail: {sectionId: this.sectionId},
    }));
  }
}

AlertsControls.TYPING_DEBOUNCE_MS = 300;

AlertsControls.reducers = {
  receiveReportNames: (state, {infos, error}, rootState) => {
    if (error) {
      const errors = [...new Set([error.message, ...(state.errors || [])])];
      return {...state, errors};
    }

    const reportNames = infos.map(t => t.name);
    const report = {
      ...state.report,
      options: OptionGroup.groupValues(reportNames),
      label: `Reports (${reportNames.length})`,
    };
    return {...state, report};
  },

  receiveSheriffs: (state, {sheriffs, error}, rootState) => {
    if (error) {
      const errors = [...new Set([error.message, ...(state.errors || [])])];
      return {...state, errors};
    }

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
