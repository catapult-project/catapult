/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './cp-loading.js';
import './cp-switch.js';
import './error-set.js';
import AlertsControls from './alerts-controls.js';
import AlertsRequest from './alerts-request.js';
import AlertsTable from './alerts-table.js';
import ChartCompound from './chart-compound.js';
import ChartTimeseries from './chart-timeseries.js';
import ExistingBugRequest from './existing-bug-request.js';
import MenuInput from './menu-input.js';
import NewBugRequest from './new-bug-request.js';
import TriageExisting from './triage-existing.js';
import TriageNew from './triage-new.js';
import groupAlerts from './group-alerts.js';
import {ElementBase, STORE} from './element-base.js';
import {CHAIN, TOGGLE, UPDATE} from './simple-redux.js';
import {autotriage} from './autotriage.js';
import {html, css} from 'lit-element';

import {
  BatchIterator,
  animationFrame,
  get,
  isDebug,
  isProduction,
  measureElement,
  plural,
  setImmutable,
  simpleGUID,
  timeout,
  transformAlert,
} from './utils.js';

const NOTIFICATION_MS = 5000;
const FULLAUTOTRIAGE_DELAY_MS = 3000;

// loadMore() below chases cursors when loading untriaged alerts until it's
// loaded enough alert groups and spent enough time waiting for the backend.
const ENOUGH_GROUPS = 100;
const ENOUGH_LOADING_MS = 60000;

const HOTKEYS = {
  HELP: '?',
  DOWN: 'j',
  UP: 'k',
  NEW_BUG: 'n',
  SELECT: 'x',
  EXPAND_GROUP: 'g',
  EXPAND_TRIAGED: 't',
  START_SORT: 's',
  AUTOTRIAGE: 'a',
  EXISTING_BUG: 'e',
  NEW_BUG: 'n',
  IGNORE: 'i',
  UNASSIGN: 'u',
  SEARCH: '/',
};

const SORT_HOTKEYS = {
  'c': 'count',
  't': 'triaged',
  'u': 'bugId',
  'r': 'startRevision',
  's': 'suite',
  'm': 'measurement',
  'a': 'master',
  'b': 'bot',
  'e': 'case',
  'd': 'deltaValue',
  'p': 'percentDeltaValue',
};

if (new Set(Object.values(HOTKEYS)).size !== Object.keys(HOTKEYS).length) {
  throw new Error('Duplicate hotkey');
}

export default class AlertsSection extends ElementBase {
  static get is() { return 'alerts-section'; }

  static get properties() {
    return {
      statePath: String,
      linkedStatePath: String,
      ...AlertsTable.properties,
      ...AlertsControls.properties,
      existingBug: Object,
      isLoading: Boolean,
      newBug: Object,
      preview: Object,
      sectionId: Number,
      selectedAlertPath: String,
      totalCount: Number,
      autotriage: Object,
      hotkeyable: Boolean,
    };
  }

  static buildState(options = {}) {
    return {
      ...AlertsTable.buildState(options),
      ...AlertsControls.buildState(options),
      existingBug: TriageExisting.buildState({}),
      isLoading: false,
      newBug: TriageNew.buildState({}),
      preview: ChartCompound.buildState(options),
      sectionId: options.sectionId || simpleGUID(),
      selectedAlertPath: undefined,
      totalCount: 0,
      autotriage: {
        fullAuto: options.fullAuto || false,
        running: false,
        bugId: 0,
        explanation: '',
      },
      hotkeyable: false,
    };
  }

  static get styles() {
    return css`
      #wrapper {
        border: 4px solid var(--background-color);
        padding: 4px;
      }

      #wrapper[hotkeyable] {
        border-color: var(--primary-color-medium);
      }

      #triage-controls {
        align-items: center;
        display: flex;
        padding-left: 24px;
        transition: background-color var(--transition-short, 0.2s),
                    color var(--transition-short, 0.2s);
      }

      #triage-controls[anySelected] {
        background-color: var(--primary-color-light, lightblue);
        color: var(--primary-color-dark, blue);
      }

      #triage-controls .button {
        background: unset;
        cursor: pointer;
        font-weight: bold;
        padding: 8px;
        text-transform: uppercase;
      }

      #triage-controls .button[disabled] {
        color: var(--neutral-color-dark, grey);
        font-weight: normal;
      }

      #count {
        padding: 8px;
        flex-grow: 1;
      }

      #autotriage {
        display: flex;
        align-items: center;
        border: 2px solid var(--primary-color-light, lightblue);
        padding: 4px;
      }

      #explanation {
        flex-grow: 1;
        text-align: center;
      }
    `;
  }

  render() {
    const selectedAlerts = AlertsTable.getSelectedAlerts(this.alertGroups);
    let anyTriaged = false;
    for (const alert of selectedAlerts) {
      if (alert.bugId) {
        anyTriaged = true;
        break;
      }
    }

    const canTriage = (selectedAlerts.length > 0) && !anyTriaged;
    const allTriaged = this.allTriaged_();
    const summary = AlertsSection.summary(
        this.showingTriaged, this.alertGroups, this.totalCount);

    const canAutotriage = isProduction() && this.sheriff &&
      this.sheriff.selectedOptions && this.sheriff.selectedOptions.length;

    let fullAutoTooltip = this.autotriage.fullAuto ?
      'Now triaging alerts completely automatically. Click to switch to ' +
      'semi-automatic, where you need to click a button to accept autotriage ' +
      'suggestions.' :
      'Now semi-automatic, where you can click a button to accept autotriage ' +
      'suggestions. Click to switch to full automatic.';
    fullAutoTooltip += '\n\nDISABLED until sheriffs approve the ' +
      'heuristics in autotriage.js';
    let autotriageLabel = 'Autotriage';
    if (this.autotriage.explanation) {
      if (this.autotriage.fullAuto) {
        autotriageLabel = this.autotriage.running ? 'Stop' : 'Start';
      } else {
        if (this.autotriage.bugId < 0) {
          autotriageLabel = 'Ignore';
        } else if (this.autotriage.bugId > 0) {
          autotriageLabel = 'Assign to ' + this.autotriage.bugId;
        } else {
          autotriageLabel = 'New Bug';
        }
      }
    }

    return html`
      <div id="wrapper" ?hotkeyable="${this.hotkeyable}">
        <alerts-controls
            id="controls"
            .statePath="${this.statePath}"
            @sources="${this.onSources_}">
        </alerts-controls>

        <error-set .errors="${this.errors}"></error-set>
        <cp-loading ?loading="${this.isLoading || this.preview.isLoading}">
        </cp-loading>

        ${(this.alertGroups && this.alertGroups.length) ? html`
          ${!canAutotriage ? '' : html`
            <div id="autotriage">
              <cp-switch
                  title="${fullAutoTooltip}"
                  disabled="true"
                  ?checked="${this.autotriage.fullAuto}"
                  @change="${this.onToggleFullAuto_}">
                Full automatic
              </cp-switch>

              <span id="explanation">
                ${!this.isLoading ? '' : html`
                  Please wait for triaged alerts to finish loading.
                `}
                <br>
                ${this.autotriage.explanation ||
                  'Select alerts in the table below to autotriage.'}
              </span>

              <raised-button
                  ?disabled="${!this.autotriage.explanation}"
                  @click="${this.onAutotriage_}">
                ${autotriageLabel}
              </raised-button>
            </div>
          `}

          <div id="triage-controls"
              ?anySelected="${this.selectedAlertsCount !== 0}">
            <div id="count">
              ${this.selectedAlertsCount} selected of ${summary}
            </div>

            ${!isProduction() ? '' : html`
              <span style="position: relative;">
                <div class="button"
                    ?disabled="${!canTriage}"
                    @click="${this.onTriageNew_}">
                  New Bug
                </div>

                <triage-new
                    tabindex="0"
                    .statePath="${this.statePath}.newBug"
                    @submit="${this.onTriageNewSubmit_}">
                </triage-new>
              </span>

              <span style="position: relative;">
                <div class="button"
                    ?disabled="${!canTriage}"
                    @click="${this.onTriageExisting_}">
                  Existing Bug
                </div>

                <triage-existing
                    tabindex="0"
                    .statePath="${this.statePath}.existingBug"
                    @submit="${this.onTriageExistingSubmit_}">
                </triage-existing>
              </span>

              <div class="button"
                  ?disabled="${!canTriage}"
                  @click="${this.onIgnore_}">
                Ignore
              </div>

              <div class="button"
                  ?disabled="${!anyTriaged}"
                  @click="${this.onUnassign_}">
                Unassign
              </div>
            `}
          </div>
        ` : html``}

        <alerts-table
            .statePath="${this.statePath}"
            @selected="${this.onSelected_}"
            @alert-click="${this.onAlertClick_}">
        </alerts-table>

        <chart-compound
            id="preview"
            ?hidden="${allTriaged}"
            .statePath="${this.statePath}.preview"
            .linkedStatePath="${this.linkedStatePath}"
            @line-count-change="${this.onPreviewLineCountChange_}">
          Select alerts using the checkboxes in the table above to preview
          their timeseries.
        </chart-compound>
      </div>
    `;
  }

  constructor() {
    super();
    this.onKeyup_ = this.onKeyup_.bind(this);
  }

  async connectedCallback() {
    super.connectedCallback();
    window.addEventListener('keyup', this.onKeyup_);
  }

  disconnectedCallback() {
    window.removeEventListener('keyup', this.onKeyup_);
    super.disconnectedCallback();
  }

  firstUpdated() {
    this.scrollIntoView(true);
    this.updateHotkeyable_();
  }

  updated(changedProperties) {
    if (changedProperties.has('alertGroups') ||
        changedProperties.has('preview')) {
      this.updateHotkeyable_();
    }
  }

  allTriaged_() {
    if (!this.alertGroups) return true;
    if (this.showingTriaged) return this.alertGroups.length === 0;
    return this.alertGroups.filter(group =>
      group.alerts.length > group.triaged.count).length === 0;
  }

  async updateHotkeyable_() {
    const thisRect = await measureElement(this);
    const midline = window.innerHeight / 2;
    STORE.dispatch(UPDATE(this.statePath, {
      hotkeyable: (thisRect.top < midline && thisRect.bottom > midline),
    }));
  }

  onScroll() {
    this.updateHotkeyable_();
  }

  async onKeyup_(event) {
    if (!this.hotkeyable) return;

    if (this.isHotkeySorting) {
      STORE.dispatch({
        type: AlertsSection.reducers.hotkeySort.name,
        statePath: this.statePath,
        key: event.key,
      });
      return;
    }

    if (event.key === HOTKEYS.AUTOTRIAGE) {
      await AlertsSection.autotriage(this.statePath);
      return;
    }

    if (event.key === HOTKEYS.EXISTING_BUG) {
      await AlertsSection.submitExistingBug(this.statePath);
      return;
    }

    if (event.key === HOTKEYS.NEW_BUG) {
      await AlertsSection.openNewBugDialog(this.statePath);
      STORE.dispatch(UPDATE(this.statePath + '.newBug', {isOpen: false}));
      await AlertsSection.submitNewBug(this.statePath);
      return;
    }

    if (event.key === HOTKEYS.IGNORE) {
      AlertsSection.ignore(this.statePath);
      return;
    }

    if (event.key === HOTKEYS.UNASSIGN) {
      await AlertsSection.changeBugId(this.statePath, 0);
      return;
    }

    if (event.key === HOTKEYS.SEARCH) {
      MenuInput.focus(this.statePath + '.sheriff');
      return;
    }

    STORE.dispatch({
      type: AlertsSection.reducers.hotkey.name,
      statePath: this.statePath,
      key: event.key,
    });

    if (event.key === HOTKEYS.SELECT) {
      AlertsSection.maybeLayoutPreview(this.statePath);
    }
  }

  async onSources_(event) {
    await AlertsSection.loadAlerts(this.statePath, event.detail.sources);
  }

  async onToggleFullAuto_(event) {
    STORE.dispatch(CHAIN(TOGGLE(this.statePath + '.autotriage.fullAuto'), {
      type: AlertsSection.reducers.autotriage.name,
      statePath: this.statePath,
    }));
  }

  async onAutotriage_(event) {
    if (!this.autotriage.fullAuto) {
      await AlertsSection.autotriage(this.statePath);
      return;
    }

    STORE.dispatch(TOGGLE(this.statePath + '.autotriage.running'));
    if (this.autotriage.running) {
      AlertsSection.fullAutotriage(this.statePath);
    }
  }

  static async fullAutotriage(statePath) {
    await timeout(FULLAUTOTRIAGE_DELAY_MS);
    let state = get(STORE.getState(), statePath);
    while (state.autotriage.running) {
      await AlertsSection.autotriage(this.statePath);
      await timeout(FULLAUTOTRIAGE_DELAY_MS);
      state = get(STORE.getState(), statePath);
    }
  }

  static async autotriage(statePath) {
    const state = get(STORE.getState(), statePath);
    if (state.autotriage.bugId) {
      await AlertsSection.changeBugId(statePath, state.autotriage.bugId);
    } else {
      await AlertsSection.openNewBugDialog(statePath);
      STORE.dispatch(UPDATE(statePath + '.newBug', {isOpen: false}));
      await AlertsSection.submitNewBug(statePath);
    }
  }

  async onUnassign_(event) {
    await AlertsSection.changeBugId(this.statePath, 0);
  }

  onTriageNew_(event) {
    // If the user is already signed in, then require-sign-in will do nothing,
    // and openNewBugDialog will do so. If the user is not already signed in,
    // then openNewBugDialog won't, and require-sign-in will start the signin
    // flow. Users can retry triaging after completing the signin flow.
    this.dispatchEvent(new CustomEvent('require-sign-in', {
      bubbles: true,
      composed: true,
    }));
    AlertsSection.openNewBugDialog(this.statePath);
  }

  onTriageExisting_(event) {
    // If the user is already signed in, then require-sign-in will do nothing,
    // and openExistingBugDialog will do so. If the user is not already signed
    // in, then openExistingBugDialog won't, and require-sign-in will start
    // the signin flow.
    this.dispatchEvent(new CustomEvent('require-sign-in', {
      bubbles: true,
      composed: true,
    }));
    AlertsSection.openExistingBugDialog(this.statePath);
  }

  onTriageNewSubmit_(event) {
    AlertsSection.submitNewBug(this.statePath);
  }

  onTriageExistingSubmit_(event) {
    AlertsSection.submitExistingBug(this.statePath);
  }

  onIgnore_(event) {
    AlertsSection.ignore(this.statePath);
  }

  onSelected_(event) {
    AlertsSection.maybeLayoutPreview(this.statePath);
    STORE.dispatch({
      type: AlertsSection.reducers.autotriage.name,
      statePath: this.statePath,
    });
  }

  onAlertClick_(event) {
    STORE.dispatch({
      type: AlertsSection.reducers.selectAlert.name,
      statePath: this.statePath,
      alertGroupIndex: event.detail.alertGroupIndex,
      alertIndex: event.detail.alertIndex,
    });
  }

  onPreviewLineCountChange_() {
    STORE.dispatch({
      type: AlertsSection.reducers.updateAlertColors.name,
      statePath: this.statePath,
    });
  }

  static storeRecentlyModifiedBugs(statePath) {
    const state = get(STORE.getState(), statePath);
    localStorage.setItem('recentlyModifiedBugs', JSON.stringify(
        state.recentlyModifiedBugs));
  }

  static async submitExistingBug(statePath) {
    METRICS.endTriage();
    METRICS.startTriage();

    let state = get(STORE.getState(), statePath);
    const triagedBugId = state.existingBug.bugId;
    STORE.dispatch(UPDATE(`${statePath}.existingBug`, {isOpen: false}));

    await AlertsSection.changeBugId(statePath, triagedBugId);

    STORE.dispatch({
      type: AlertsSection.reducers.showTriagedExisting.name,
      statePath,
      triagedBugId,
    });
    await AlertsSection.storeRecentlyModifiedBugs(statePath);

    // showTriagedExisting sets hasTriagedNew and triagedBugId, causing
    // alerts-controls to display a notification. Wait a few seconds for the
    // user to notice the notification, then automatically hide it. The user
    // will still be able to access the bug by clicking Recent Bugs in
    // alerts-controls.
    await timeout(NOTIFICATION_MS);
    state = get(STORE.getState(), statePath);
    if (!state || (state.triagedBugId !== triagedBugId)) return;
    STORE.dispatch(UPDATE(statePath, {
      hasTriagedExisting: false,
      triagedBugId: 0,
    }));
  }

  static async changeBugId(statePath, bugId) {
    STORE.dispatch(UPDATE(statePath, {isLoading: true}));
    const state = get(STORE.getState(), statePath);
    const selectedAlerts = AlertsTable.getSelectedAlerts(
        state.alertGroups);
    const alertKeys = new Set(selectedAlerts.map(a => a.key));

    STORE.dispatch({
      type: AlertsSection.reducers.removeOrUpdateAlerts.name,
      statePath,
      alertKeys,
      bugId,
    });

    AlertsSection.selectFirstGroup(statePath);

    try {
      const request = new ExistingBugRequest({alertKeys, bugId});
      await request.response;
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error(err);
    }
    STORE.dispatch(UPDATE(statePath, {isLoading: false}));
  }

  static async ignore(statePath) {
    let state = get(STORE.getState(), statePath);
    const alerts = AlertsTable.getSelectedAlerts(state.alertGroups);
    const ignoredCount = alerts.length;
    await AlertsSection.changeBugId(statePath,
        ExistingBugRequest.IGNORE_BUG_ID);

    STORE.dispatch(UPDATE(statePath, {
      hasTriagedExisting: false,
      hasTriagedNew: false,
      hasIgnored: true,
      ignoredCount,
    }));

    // Setting hasIgnored and ignoredCount causes alerts-controls to display a
    // notification. Wait a few seconds for the user to notice the
    // notification, then automatically hide it. The user can still access
    // ignored alerts by toggling New Only to New and Triaged in
    // alerts-controls.
    await timeout(NOTIFICATION_MS);
    state = get(STORE.getState(), statePath);
    if (!state || (state.ignoredCount !== ignoredCount)) return;
    STORE.dispatch(UPDATE(statePath, {
      hasIgnored: false,
      ignoredCount: 0,
    }));
  }

  static async openNewBugDialog(statePath) {
    let userEmail = STORE.getState().userEmail;
    if (isDebug()) {
      userEmail = 'you@chromium.org';
    }
    if (!userEmail) return;
    STORE.dispatch({
      type: AlertsSection.reducers.openNewBugDialog.name,
      statePath,
      userEmail,
    });
  }

  static async openExistingBugDialog(statePath) {
    let userEmail = STORE.getState().userEmail;
    if (isDebug()) {
      userEmail = 'you@chromium.org';
    }
    if (!userEmail) return;
    STORE.dispatch({
      type: AlertsSection.reducers.openExistingBugDialog.name,
      statePath,
    });
  }

  static async selectFirstGroup(statePath) {
    const state = get(STORE.getState(), statePath);
    STORE.dispatch(CHAIN({
      type: AlertsTable.reducers.selectAlert.name,
      statePath,
      alertGroupIndex: 0,
      alertIndex: state.alertGroups[0].alerts.findIndex(a => !a.bugId),
    }, {
      type: AlertsSection.reducers.autotriage.name,
      statePath,
    }));
    AlertsSection.maybeLayoutPreview(statePath);
  }

  static async submitNewBug(statePath) {
    METRICS.endTriage();
    METRICS.startTriage();

    STORE.dispatch(UPDATE(statePath, {isLoading: true}));

    let state = get(STORE.getState(), statePath);
    const selectedAlerts = AlertsTable.getSelectedAlerts(
        state.alertGroups);
    const alertKeys = new Set(selectedAlerts.map(a => a.key));

    // Remove selected alerts.
    STORE.dispatch({
      type: AlertsSection.reducers.removeOrUpdateAlerts.name,
      statePath,
      alertKeys,
      bugId: '[creating]',
    });

    AlertsSection.selectFirstGroup(statePath);

    let bugId;
    try {
      const request = new NewBugRequest({
        alertKeys,
        ...state.newBug,
        labels: state.newBug.labels.filter(
            x => x.isEnabled).map(x => x.name),
        components: state.newBug.components.filter(
            x => x.isEnabled).map(x => x.name),
      });
      const summary = state.newBug.summary;
      bugId = await request.response;
      STORE.dispatch({
        type: AlertsSection.reducers.showTriagedNew.name,
        statePath,
        bugId,
        summary,
      });
      await AlertsSection.storeRecentlyModifiedBugs(statePath);

      STORE.dispatch({
        type: AlertsSection.reducers.removeOrUpdateAlerts.name,
        statePath,
        alertKeys,
        bugId,
      });
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error(err);
    }
    STORE.dispatch(UPDATE(statePath, {isLoading: false}));

    if (bugId === undefined) return;

    // showTriagedNew sets hasTriagedNew and triagedBugId, causing
    // alerts-controls to display a notification. Wait a few seconds for the
    // user to notice the notification, then automatically hide it. The user
    // will still be able to access the new bug by clicking Recent Bugs in
    // alerts-controls.
    await timeout(NOTIFICATION_MS);
    state = get(STORE.getState(), statePath);
    if (!state || state.triagedBugId !== bugId) return;
    STORE.dispatch(UPDATE(statePath, {
      hasTriagedNew: false,
      triagedBugId: 0,
    }));
  }

  static async loadAlerts(statePath, sources) {
    const started = performance.now();
    STORE.dispatch({
      type: AlertsSection.reducers.startLoadingAlerts.name,
      statePath,
      started,
    });
    if (sources.length) {
      MenuInput.blurAll();
    } else {
      AlertsSection.maybeLayoutPreview(statePath);
    }

    // When a request for untriaged alerts finishes, a request is started for
    // overlapping triaged alerts. This is used to avoid fetching the same
    // triaged alerts multiple times.
    let triagedMaxStartRevision;

    METRICS.startLoadAlerts();

    // Use a BatchIterator to batch AlertsRequest.response.
    // Each batch of results is handled in handleBatch(), then displayed by
    // dispatching reducers.receiveAlerts.
    // loadMore() may add more AlertsRequests to the BatchIterator to chase
    // datastore query cursors.
    const batches = new BatchIterator(sources.map(wrapRequest));

    // Wait one tick to let the browser start the first AlertsRequests, then,
    // while waiting for the server to respond, initialize the memory
    // relationships.
    await Promise.resolve();
    d.getMemoryRelatedNames();

    for await (const {results, errors} of batches) {
      let state = get(STORE.getState(), statePath);
      if (!state || state.started !== started) {
        // Abandon this loadAlerts if the section was closed or if
        // loadAlerts() was called again before this one finished.
        return;
      }

      const {alerts, nextRequests, triagedRequests, totalCount} = handleBatch(
          results, state.showingTriaged);
      if (alerts.length || errors.length) {
        STORE.dispatch({
          type: AlertsSection.reducers.receiveAlerts.name,
          statePath,
          alerts,
          errors,
          totalCount,
        });
        METRICS.endLoadAlerts();
      }
      state = get(STORE.getState(), statePath);
      if (!state || state.started !== started) return;

      triagedMaxStartRevision = loadMore(
          batches, state.alertGroups, nextRequests, triagedRequests,
          triagedMaxStartRevision, started);
      await animationFrame();
    }

    STORE.dispatch({
      type: AlertsSection.reducers.finalizeAlerts.name,
      statePath,
    });

    const state = get(STORE.getState(), statePath);
    if (!state) return;
    if (state.preview && state.preview.lineDescriptors &&
        state.preview.lineDescriptors.length) {
      return;
    }

    AlertsSection.maybeLayoutPreview(statePath);
  }

  static async layoutPreview(statePath) {
    const state = get(STORE.getState(), statePath);
    const alerts = AlertsTable.getSelectedAlerts(state.alertGroups);
    const lineDescriptors = alerts.map(AlertsSection.computeLineDescriptor);
    if (lineDescriptors.length === 1) {
      lineDescriptors.push({
        ...lineDescriptors[0],
        buildType: 'ref',
      });
    }
    STORE.dispatch(UPDATE(`${statePath}.preview`, {lineDescriptors}));
  }

  static async maybeLayoutPreview(statePath) {
    const state = get(STORE.getState(), statePath);
    if (!state || !state.selectedAlertsCount) {
      STORE.dispatch(UPDATE(`${statePath}.preview`, {lineDescriptors: []}));
      return;
    }

    AlertsSection.layoutPreview(statePath);
  }

  static summary(showingTriaged, alertGroups, totalCount) {
    if (!alertGroups ||
        (alertGroups === AlertsTable.placeholderAlertGroups())) {
      return '0 alerts';
    }
    let groupCount = 0;
    let displayedCount = 0;
    for (const group of alertGroups) {
      if (showingTriaged) {
        ++groupCount;
        displayedCount += group.alerts.length;
      } else if (group.alerts.length > group.triaged.count) {
        ++groupCount;
        displayedCount += group.alerts.length - group.triaged.count;
      }
    }
    totalCount = Math.max(totalCount, displayedCount);
    return (
      `${displayedCount} displayed in ` +
      `${groupCount} group${plural(groupCount)} of ` +
      `${totalCount} alert${plural(totalCount)}`);
  }

  static matchesOptions(state, options) {
    if (!options || !state || !state.report || !state.sheriff || !state.bug) {
      return false;
    }
    if (!tr.b.setsEqual(new Set(options.reports),
        new Set(state.report.selectedOptions))) {
      return false;
    }
    if (!tr.b.setsEqual(new Set(options.sheriffs),
        new Set(state.sheriff.selectedOptions))) {
      return false;
    }
    if (!tr.b.setsEqual(new Set(options.bugs),
        new Set(state.bug.selectedOptions))) {
      return false;
    }
    return true;
  }

  static newStateOptionsFromQueryParams(queryParams) {
    return {
      sheriffs: queryParams.getAll('sheriff').map(
          sheriffName => sheriffName.replace(/_/g, ' ')),
      bugs: queryParams.getAll('bug'),
      reports: queryParams.getAll('ar'),
      minRevision: queryParams.get('minRev') || queryParams.get('rev'),
      maxRevision: queryParams.get('maxRev') || queryParams.get('rev'),
      sortColumn: queryParams.get('sort') || 'startRevision',
      showingImprovements: ((queryParams.get('improvements') !== null) ||
        (queryParams.get('bug') !== null)),
      showingTriaged: ((queryParams.get('triaged') !== null) ||
        (queryParams.get('bug') !== null)),
      sortDescending: queryParams.get('descending') !== null,
      fullAuto: queryParams.get('fa') !== null,
    };
  }

  static isEmpty(state) {
    if (!state) return true;
    if (state.sheriff && state.sheriff.selectedOptions &&
        state.sheriff.selectedOptions.length) {
      return false;
    }
    if (state.bug && state.bug.selectedOptions &&
        state.bug.selectedOptions.length) {
      return false;
    }
    if (state.report && state.report.selectedOptions &&
        state.report.selectedOptions.length) {
      return false;
    }
    if (state.minRevision && state.minRevision.match(/^\d+$/)) {
      return false;
    }
    if (state.maxRevision && state.maxRevision.match(/^\d+$/)) {
      return false;
    }
    return true;
  }

  static getSessionState(state) {
    return {
      sheriffs: state.sheriff.selectedOptions,
      bugs: state.bug.selectedOptions,
      showingImprovements: state.showingImprovements,
      showingTriaged: state.showingTriaged,
      sortColumn: state.sortColumn,
      sortDescending: state.sortDescending,
      fullAuto: state.autotriage.fullAuto,
    };
  }

  static getRouteParams(state) {
    const queryParams = new URLSearchParams();
    for (const sheriff of state.sheriff.selectedOptions) {
      queryParams.append('sheriff', sheriff.replace(/ /g, '_'));
    }
    for (const bug of state.bug.selectedOptions) {
      queryParams.append('bug', bug);
    }
    for (const name of state.report.selectedOptions) {
      queryParams.append('ar', name);
    }

    const minRev = state.minRevision && state.minRevision.match(/^\d+$/);
    const maxRev = state.maxRevision && state.maxRevision.match(/^\d+$/);
    if ((minRev || maxRev) &&
        !queryParams.get('sheriff') &&
        !queryParams.get('bug') &&
        !queryParams.get('ar')) {
      queryParams.set('alerts', '');
    }
    if (minRev && maxRev && state.minRevision === state.maxRevision) {
      queryParams.set('rev', state.minRevision);
    } else {
      if (minRev) {
        queryParams.set('minRev', state.minRevision);
      }
      if (maxRev) {
        queryParams.set('maxRev', state.maxRevision);
      }
    }

    // #bug implies #improvements and #triaged
    if (state.showingImprovements && !queryParams.get('bug')) {
      queryParams.set('improvements', '');
    }
    if (state.showingTriaged && !queryParams.get('bug')) {
      queryParams.set('triaged', '');
    }
    if (state.sortColumn !== 'startRevision') {
      queryParams.set('sort', state.sortColumn);
    }
    if (state.autotriage.fullAuto) {
      queryParams.set('fa', '');
    }
    if (state.sortDescending) queryParams.set('descending', '');
    return queryParams;
  }

  static computeLineDescriptor(alert) {
    return {
      baseUnit: alert.baseUnit,
      suites: [alert.suite],
      measurement: alert.measurement,
      bots: [alert.master + ':' + alert.bot],
      cases: [alert.case],
      statistic: alert.statistic,
      buildType: 'test',
    };
  }
}

async function wrapRequest(body) {
  const request = new AlertsRequest({body});
  const response = await request.response;
  return {body, response};
}

// The BatchIterator in loadAlerts() yielded a batch of results.
// Collect all alerts from all batches into `alerts`.
// Chase cursors in `nextRequests`.
// Fetch triaged alerts when a request for untriaged alerts returns.
function handleBatch(results, showingTriaged) {
  const alerts = [];
  const nextRequests = [];
  const triagedRequests = [];
  let totalCount = 0;
  for (const {body, response} of results) {
    alerts.push.apply(alerts, response.anomalies);

    if (body.count_limit) totalCount += response.count;

    const cursor = response.next_cursor;
    if (cursor) {
      const request = {...body, cursor};
      delete request.count_limit;
      nextRequests.push(request);
    }

    if (!showingTriaged && body.bug_id === '') {
      // Prepare to fetch triaged alerts for the untriaged alerts that
      // were just received.
      const request = {...body, bug_id: '*'};
      delete request.recovered;
      delete request.count_limit;
      delete request.cursor;
      delete request.is_improvement;
      triagedRequests.push(request);
    }
  }

  return {alerts, nextRequests, triagedRequests, totalCount};
}

// This function may add requests to `batches`.
// See handleBatch for `nextRequests` and `triagedRequests`.
function loadMore(batches, alertGroups, nextRequests, triagedRequests,
    triagedMaxStartRevision, started) {
  const minStartRevision = tr.b.math.Statistics.min(
      alertGroups, group => tr.b.math.Statistics.min(
          group.alerts, a => a.startRevision));

  if (!triagedMaxStartRevision ||
      (minStartRevision < triagedMaxStartRevision)) {
    for (const request of triagedRequests) {
      if (minStartRevision) {
        request.min_start_revision = minStartRevision;
      }
      if (triagedMaxStartRevision) {
        request.max_start_revision = triagedMaxStartRevision;
      }
      batches.add(wrapRequest(request));
    }
  }

  for (const next of nextRequests) {
    // Always chase down cursors for triaged alerts.
    // Limit the number of alertGroups displayed to prevent OOM.
    if (next.bug_id === '*' ||
        (alertGroups.length < ENOUGH_GROUPS &&
        ((performance.now() - started) < ENOUGH_LOADING_MS))) {
      batches.add(wrapRequest(next));
    }
  }

  return minStartRevision;
}

AlertsSection.reducers = {
  selectAlert: (state, action, rootState) => {
    if (state.alertGroups === AlertsTable.placeholderAlertGroups()) {
      return state;
    }
    const alertPath =
      `alertGroups.${action.alertGroupIndex}.alerts.${action.alertIndex}`;
    const alert = get(state, alertPath);
    if (!alert.isSelected) {
      state = setImmutable(
          state, `${alertPath}.isSelected`, true);
    }
    if (state.selectedAlertPath === alertPath) {
      return {
        ...state,
        selectedAlertPath: undefined,
        preview: {
          ...state.preview,
          lineDescriptors: AlertsTable.getSelectedAlerts(
              state.alertGroups).map(AlertsSection.computeLineDescriptor),
        },
      };
    }
    return {
      ...state,
      selectedAlertPath: alertPath,
      preview: {
        ...state.preview,
        lineDescriptors: [AlertsSection.computeLineDescriptor(alert)],
      },
    };
  },

  showTriagedNew: (state, action, rootState) => {
    return {
      ...state,
      hasTriagedExisting: false,
      hasTriagedNew: true,
      hasIgnored: false,
      triagedBugId: action.bugId,
      recentlyModifiedBugs: [
        {
          id: action.bugId,
          summary: action.summary,
        },
        ...state.recentlyModifiedBugs,
      ],
    };
  },

  showTriagedExisting: (state, action, rootState) => {
    const recentlyModifiedBugs = state.recentlyModifiedBugs.filter(bug =>
      bug.id !== action.triagedBugId);
    let triagedBugSummary = '(TODO fetch bug summary)';
    for (const bug of rootState.recentPerformanceBugs) {
      if (bug.id === action.triagedBugId) {
        triagedBugSummary = bug.summary;
        break;
      }
    }
    recentlyModifiedBugs.unshift({
      id: action.triagedBugId,
      summary: triagedBugSummary,
    });
    return {
      ...state,
      hasTriagedExisting: true,
      hasTriagedNew: false,
      hasIgnored: false,
      triagedBugId: action.triagedBugId,
      recentlyModifiedBugs,
    };
  },

  updateAlertColors: (state, action, rootState) => {
    const colorByDescriptor = new Map();
    for (const line of state.preview.chartLayout.lines) {
      colorByDescriptor.set(ChartTimeseries.stringifyDescriptor(
          line.descriptor), line.color);
    }

    function updateAlert(alert) {
      const descriptor = ChartTimeseries.stringifyDescriptor(
          AlertsSection.computeLineDescriptor(alert));
      const color = colorByDescriptor.get(descriptor);
      return {...alert, color};
    }

    const alertGroups = state.alertGroups.map(alertGroup => {
      const alerts = alertGroup.alerts.map(updateAlert);
      return {...alertGroup, alerts};
    });
    return {...state, alertGroups};
  },

  updateSelectedAlertsCount: state => {
    const selectedAlertsCount = AlertsTable.getSelectedAlerts(
        state.alertGroups).length;
    return {...state, selectedAlertsCount};
  },

  removeAlerts: (state, {alertKeys}, rootState) => {
    const alertGroups = [];
    for (const group of state.alertGroups) {
      const alerts = group.alerts.filter(a => !alertKeys.has(a.key));
      if (alerts.filter(a => !a.bugId).length) {
        alertGroups.push({...group, alerts});
      }
    }
    state = {...state, alertGroups};
    return AlertsSection.reducers.updateSelectedAlertsCount(state);
  },

  updateBugId: (state, {alertKeys, bugId}, rootState) => {
    if (bugId === 0) bugId = '';
    const alertGroups = state.alertGroups.map(alertGroup => {
      const alerts = alertGroup.alerts.map(a =>
        (alertKeys.has(a.key) ? {...a, bugId} : a));
      return {...alertGroup, alerts};
    });
    state = {...state, alertGroups};
    return AlertsSection.reducers.updateSelectedAlertsCount(state);
  },

  removeOrUpdateAlerts: (state, action, rootState) => {
    if (state.showingTriaged || action.bugId === 0) {
      return AlertsSection.reducers.updateBugId(state, action, rootState);
    }
    return AlertsSection.reducers.removeAlerts(state, action, rootState);
  },

  openNewBugDialog: (state, action, rootState) => {
    const alerts = AlertsTable.getSelectedAlerts(state.alertGroups);
    if (alerts.length === 0) return state;
    const newBug = TriageNew.buildState({
      isOpen: true, alerts, cc: action.userEmail,
    });
    return {...state, newBug};
  },

  openExistingBugDialog: (state, action, rootState) => {
    const alerts = AlertsTable.getSelectedAlerts(state.alertGroups);
    if (alerts.length === 0) return state;
    return {
      ...state,
      existingBug: {
        ...state.existingBug,
        ...TriageExisting.buildState({alerts, isOpen: true}),
      },
    };
  },

  receiveAlerts: (state, {alerts, errors, totalCount}, rootState) => {
    errors = errors.map(e => e.message);
    errors = [...new Set([...state.errors, ...errors])];
    state = {...state, errors};

    // |alerts| are all new.
    // Group them together with previously-received alerts from
    // state.alertGroups[].alerts.
    alerts = alerts.map(transformAlert);
    if (state.alertGroups !== AlertsTable.placeholderAlertGroups()) {
      for (const alertGroup of state.alertGroups) {
        alerts.push(...alertGroup.alerts);
      }
    }

    // Automatically select all alerts for bugs.
    if (state.bug.selectedOptions.length > 0 &&
        state.sheriff.selectedOptions.length === 0 &&
        state.report.selectedOptions.length === 0) {
      for (const alert of alerts) {
        alert.isSelected = true;
      }
    }

    if (!alerts.length) {
      return state;
      // Wait till finalizeAlerts to display the happy cat.
    }

    // The user may have already selected and/or triaged some alerts, so keep
    // that information, just re-group the alerts.
    const expandedGroupAlertKeys = new Set();
    const expandedTriagedAlertKeys = new Set();
    for (const group of state.alertGroups) {
      if (group.isExpanded) {
        expandedGroupAlertKeys.add(group.alerts[0].key);
      }
      if (group.triaged.isExpanded) {
        expandedTriagedAlertKeys.add(group.alerts[0].key);
      }
    }

    const groupBugs = state.showingTriaged && (
      state.bug.selectedOptions.length === 1);
    let alertGroups = groupAlerts(alerts, groupBugs);
    alertGroups = alertGroups.map((alerts, groupIndex) => {
      let isExpanded = false;
      let isTriagedExpanded = false;
      for (const a of alerts) {
        if (expandedGroupAlertKeys.has(a.key)) isExpanded = true;
        if (expandedTriagedAlertKeys.has(a.key)) isTriagedExpanded = true;
      }

      return {
        alerts,
        isExpanded,
        triaged: {
          isExpanded: isTriagedExpanded,
          count: alerts.filter(a => a.bugId).length,
        }
      };
    });

    if (!state.showingTriaged && state.sheriff.selectedOptions.length) {
      // Remove completely-triaged groups to save memory.
      alertGroups = alertGroups.filter(group =>
        group.alerts.length > group.triaged.count);
      if (!alertGroups.length) {
        return state;
        // Wait till finalizeAlerts to display the happy cat.
      }
    }

    alertGroups = AlertsTable.sortGroups(
        alertGroups, state.sortColumn, state.sortDescending,
        state.showingTriaged);

    if (totalCount) {
      state = {...state, totalCount};
    }

    // Don't automatically select the first group. Users often want to sort
    // the table by some column before previewing any alerts.

    state = {...state, alertGroups};
    state = AlertsSection.reducers.updateColumns(state);
    state = AlertsSection.reducers.updateSelectedAlertsCount(state);
    state = AlertsSection.reducers.autotriage(state);
    return state;
  },

  autotriage: (state, action, rootState) => {
    if (state.bug.selectedOptions.length ||
        state.report.selectedOptions.length ||
        !state.sheriff.selectedOptions.length ||
        state.showingTriaged) {
      return state;
    }

    const untriagedAlerts = [];
    const triagedAlerts = [];
    for (const alertGroup of state.alertGroups) {
      let anyInGroup = false;
      for (const alert of alertGroup.alerts) {
        if (!alert.isSelected || alert.bugId) continue;
        untriagedAlerts.push(alert);
        anyInGroup = true;
      }
      if (anyInGroup) {
        for (const alert of alertGroup.alerts) {
          if (!alert.bugId) continue;
          triagedAlerts.push(alert);
        }
      }
    }

    if (!untriagedAlerts.length) {
      return {
        ...state,
        autotriage: {
          ...state.autotriage,
          bugId: 0,
          explanation: '',
        },
      };
    }

    return {
      ...state,
      autotriage: {
        ...state.autotriage,
        ...autotriage(untriagedAlerts, triagedAlerts),
      },
    };
  },

  finalizeAlerts: (state, action, rootState) => {
    state = {...state, isLoading: false};
    if (state.alertGroups === AlertsTable.placeholderAlertGroups() &&
        (state.sheriff.selectedOptions.length ||
          state.bug.selectedOptions.length ||
          state.report.selectedOptions.length)) {
      state = {...state, alertGroups: []};
    }
    return state;
  },

  updateColumns: (state, action, rootState) => {
    // Hide the Triaged, Bug, Master, and Test Case columns if they're boring.
    let showBugColumn = false;
    let showTriagedColumn = false;
    const masters = new Set();
    const cases = new Set();
    for (const group of state.alertGroups) {
      if (group.triaged.count < group.alerts.length) {
        showTriagedColumn = true;
      }
      for (const alert of group.alerts) {
        if (alert.bugId) {
          showBugColumn = true;
        }
        masters.add(alert.master);
        cases.add(alert.case);
      }
    }
    if (state.showingTriaged) showTriagedColumn = false;

    return {
      ...state,
      showBugColumn,
      showMasterColumn: masters.size > 1,
      showTestCaseColumn: cases.size > 1,
      showTriagedColumn,
    };
  },

  startLoadingAlerts: (state, {started}, rootState) => {
    return {
      ...state,
      errors: [],
      alertGroups: AlertsTable.placeholderAlertGroups(),
      isLoading: true,
      started,
      totalCount: 0,
    };
  },

  hotkey: (state, {key}, rootState) => {
    if (key === HOTKEYS.HELP) return {...state, isHelping: !state.isHelping};
    if (key === HOTKEYS.DOWN) return AlertsSection.reducers.cursorDown(state);
    if (key === HOTKEYS.UP) return AlertsSection.reducers.cursorUp(state);
    if (key === HOTKEYS.SELECT) {
      return AlertsSection.reducers.selectCursor(state);
    }
    if (key === HOTKEYS.EXPAND_GROUP) {
      return AlertsSection.reducers.expandCursor(state);
    }
    if (key === HOTKEYS.EXPAND_TRIAGED) {
      return AlertsSection.reducers.expandTriagedCursor(state);
    }
    if (key === HOTKEYS.START_SORT) {
      return AlertsSection.reducers.startSort(state);
    }
    return state;
  },

  hotkeySort: (state, {key}, rootState) => {
    if (state.alertGroups === AlertsTable.placeholderAlertGroups()) {
      return state;
    }

    state = {...state, isHotkeySorting: false};
    const sortColumn = SORT_HOTKEYS[key];
    if (!sortColumn) return state;
    return AlertsTable.reducers.sort(state, {sortColumn}, rootState);
  },

  cursorDown: (state) => {
    if (state.alertGroups === AlertsTable.placeholderAlertGroups()) {
      return state;
    }

    let [groupIndex, alertIndex] = state.cursor || [
      state.alertGroups.length - 1,
      state.alertGroups[state.alertGroups.length - 1].alerts.length,
    ];
    ++alertIndex;
    if (alertIndex >= state.alertGroups[groupIndex].alerts.length) {
      groupIndex = (groupIndex + 1) % state.alertGroups.length;
      alertIndex = 0;
    }
    while (!AlertsTable.shouldDisplayAlert(false, state.showingTriaged,
        state.alertGroups[groupIndex], alertIndex)) {
      ++alertIndex;
      if (alertIndex >= state.alertGroups[groupIndex].alerts.length) {
        groupIndex = (groupIndex + 1) % state.alertGroups.length;
        alertIndex = 0;
      }
    }
    return {...state, cursor: [groupIndex, alertIndex]};
  },

  cursorUp: (state) => {
    if (state.alertGroups === AlertsTable.placeholderAlertGroups()) {
      return state;
    }

    let [groupIndex, alertIndex] = state.cursor || [0, 0];
    --alertIndex;
    if (alertIndex < 0) {
      --groupIndex;
      while (groupIndex < 0) {
        groupIndex += state.alertGroups.length;
      }
      alertIndex = state.alertGroups[groupIndex].alerts.length - 1;
    }
    while (!AlertsTable.shouldDisplayAlert(false, state.showingTriaged,
        state.alertGroups[groupIndex], alertIndex)) {
      --alertIndex;
      if (alertIndex < 0) {
        --groupIndex;
        while (groupIndex < 0) {
          groupIndex += state.alertGroups.length;
        }
        alertIndex = state.alertGroups[groupIndex].alerts.length - 1;
      }
    }
    return {...state, cursor: [groupIndex, alertIndex]};
  },

  selectCursor: (state) => {
    if (state.alertGroups === AlertsTable.placeholderAlertGroups() ||
        !state.cursor) {
      return state;
    }

    state = AlertsTable.reducers.selectAlert(state, {
      alertGroupIndex: state.cursor[0],
      alertIndex: state.cursor[1],
    });
    state = AlertsSection.reducers.autotriage(state);
    return state;
  },

  expandCursor: (state) => {
    if (state.alertGroups === AlertsTable.placeholderAlertGroups()) {
      return state;
    }

    if (!state.cursor) return state;
    const path = `alertGroups.${state.cursor[0]}.isExpanded`;
    return setImmutable(state, path, e => !e);
  },

  expandTriagedCursor: (state) => {
    if (state.alertGroups === AlertsTable.placeholderAlertGroups()) {
      return state;
    }

    if (!state.cursor) return state;
    const path = `alertGroups.${state.cursor[0]}.triaged.isExpanded`;
    return setImmutable(state, path, e => !e);
  },

  startSort: (state) => {
    if (state.alertGroups === AlertsTable.placeholderAlertGroups()) {
      return state;
    }

    return {...state, isHotkeySorting: true};
  },
};

ElementBase.register(AlertsSection);
