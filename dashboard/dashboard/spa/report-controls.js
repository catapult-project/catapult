/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './cp-icon.js';
import './cp-input.js';
import './raised-button.js';
import MenuInput from './menu-input.js';
import OptionGroup from './option-group.js';
import ReportNamesRequest from './report-names-request.js';
import {ElementBase, STORE} from './element-base.js';
import {UPDATE} from './simple-redux.js';
import {html, css} from 'lit-element';
import {get, isDebug, simpleGUID} from './utils.js';

export default class ReportControls extends ElementBase {
  static get is() { return 'report-controls'; }

  static get properties() {
    return {
      statePath: String,
      milestone: Number,
      minRevision: Number,
      maxRevision: Number,
      minRevisionInput: String,
      maxRevisionInput: String,
      sectionId: Number,
      source: Object,
    };
  }

  static buildState(options = {}) {
    return {
      milestone: parseInt(options.milestone) ||
        ReportControls.CURRENT_MILESTONE,
      minRevision: options.minRevision,
      maxRevision: options.maxRevision,
      minRevisionInput: options.minRevision,
      maxRevisionInput: options.maxRevision,
      sectionId: options.sectionId || simpleGUID(),
      source: MenuInput.buildState({
        label: 'Reports (loading)',
        options: [
          ReportControls.DEFAULT_NAME,
          ReportControls.CREATE,
        ],
        selectedOptions: options.sources ? options.sources : [
          ReportControls.DEFAULT_NAME,
        ],
      }),
    };
  }

  static get styles() {
    return css`
      :host {
        display: flex;
        align-items: center;
      }

      #source {
        width: 250px;
      }

      #prev-mstone,
      #next-mstone {
        font-size: larger;
      }

      #alerts {
        color: var(--primary-color-dark);
      }

      #min-revision {
        margin-right: 8px;
      }

      #min-revision,
      #max-revision {
        width: 84px;
      }

      #close {
        align-self: flex-start;
        cursor: pointer;
        flex-shrink: 0;
      }

      .spacer {
        flex-grow: 1;
      }
    `;
  }

  render() {
    return html`
      <menu-input id="source" .statePath="${this.statePath}.source">
      </menu-input>

      <raised-button
          id="alerts"
          title="Alerts"
          @click="${this.onAlerts_}">
        <cp-icon icon="alert"></cp-icon>
        <span class="nav_button_label">
          Alerts
        </span>
      </raised-button>

      <span class="spacer">&nbsp;</span>

      <raised-button
          id="prev-mstone"
          ?disabled="${this.milestone <= (MIN_MILESTONE + 1)}"
          @click="${this.onPreviousMilestone_}">
        M${this.milestone - ((this.maxRevision === 'latest') ? 1 : 2)}
        <cp-icon icon="left"></cp-icon>
      </raised-button>

      <cp-input
          id="min-revision"
          .value="${this.minRevisionInput}"
          label="Min Revision"
          @keyup="${this.onMinRevisionKeyup_}">
      </cp-input>

      <cp-input
          id="max-revision"
          .value="${this.maxRevisionInput}"
          label="Max Revision"
          @keyup="${this.onMaxRevisionKeyup_}">
      </cp-input>

      <raised-button
          id="next-mstone"
          ?disabled="${this.milestone >= ReportControls.CURRENT_MILESTONE}"
          @click="${this.onNextMilestone_}">
        <cp-icon icon="right"></cp-icon>
        M${this.milestone + 1}
      </raised-button>

      <span class="spacer">&nbsp;</span>

      <cp-icon id="close" icon="close" @click="${this.onCloseSection_}">
      </cp-icon>
    `;
  }

  firstUpdated() {
    ReportControls.connected(this.statePath);
  }

  static async connected(statePath) {
    await ReportControls.loadSources(statePath);

    let state = get(STORE.getState(), statePath);
    if (state.minRevision === undefined ||
        state.maxRevision === undefined) {
      STORE.dispatch({
        type: ReportControls.reducers.selectMilestone.name,
        statePath,
        milestone: state.milestone,
      });
      state = get(STORE.getState(), statePath);
    }

    if (state.source.selectedOptions.length === 0) {
      MenuInput.focus(statePath + '.source');
    }
  }

  static async loadSources(statePath) {
    try {
      const reportTemplateInfos = await new ReportNamesRequest().response;
      const reportNames = reportTemplateInfos.map(t => t.name);
      STORE.dispatch({
        type: ReportControls.reducers.receiveSourceOptions.name,
        statePath,
        reportNames,
      });
    } catch (err) {
      STORE.dispatch(UPDATE(statePath, {errors: [err.message]}));
    }
  }

  stateChanged(rootState) {
    this.userEmail = rootState.userEmail;
    super.stateChanged(rootState);
  }

  async onCloseSection_() {
    await this.dispatchEvent(new CustomEvent('close-section', {
      bubbles: true,
      composed: true,
      detail: {sectionId: this.sectionId},
    }));
  }

  onPreviousMilestone_() {
    STORE.dispatch({
      type: ReportControls.reducers.selectMilestone.name,
      statePath: this.statePath,
      milestone: this.milestone - 1,
    });
  }

  async onNextMilestone_() {
    STORE.dispatch({
      type: ReportControls.reducers.selectMilestone.name,
      statePath: this.statePath,
      milestone: this.milestone + 1,
    });
  }

  async onAlerts_(event) {
    this.dispatchEvent(new CustomEvent('alerts', {
      bubbles: true,
      composed: true,
      detail: {
        options: {
          reports: this.source.selectedOptions,
          showingTriaged: true,
          minRevision: '' + this.minRevisionInput,
          maxRevision: '' + this.maxRevisionInput,
        },
      },
    }));
  }

  async onMinRevisionKeyup_(event) {
    await ReportControls.setMinRevision(this.statePath, event.target.value);
  }

  async onMaxRevisionKeyup_(event) {
    await ReportControls.setMaxRevision(this.statePath, event.target.value);
  }

  static async setMinRevision(statePath, minRevisionInput) {
    STORE.dispatch(UPDATE(statePath, {minRevisionInput}));
    if (!minRevisionInput.match(/^\d{6}$/)) return;
    STORE.dispatch(UPDATE(statePath, {minRevision: minRevisionInput}));
  }

  static async setMaxRevision(statePath, maxRevisionInput) {
    STORE.dispatch(UPDATE(statePath, {maxRevisionInput}));
    if (!maxRevisionInput.match(/^\d{6}$/)) return;
    STORE.dispatch(UPDATE(statePath, {maxRevision: maxRevisionInput}));
  }
}

// http://crbug/936507
ReportControls.CHROMIUM_MILESTONES = {
  // https://omahaproxy.appspot.com/
  // Does not support M<=63
  64: 520840,
  65: 530369,
  66: 540276,
  67: 550428,
  68: 561733,
  69: 576753,
  70: 587811,
  71: 599034,
  72: 612437,
  73: 625896,
  74: 638880,
  75: 652427,
};

ReportControls.CURRENT_MILESTONE = Object.keys(
    ReportControls.CHROMIUM_MILESTONES).reduce((a, b) => Math.max(a, b));
const MIN_MILESTONE = Object.keys(ReportControls.CHROMIUM_MILESTONES).reduce(
    (a, b) => Math.min(a, b));

ReportControls.DEFAULT_NAME = 'Chromium Performance Overview';
ReportControls.CREATE = '[Create new report]';

ReportControls.reducers = {
  selectMilestone: (state, {milestone}, rootState) => {
    const maxRevision = (milestone === ReportControls.CURRENT_MILESTONE) ?
      'latest' : ReportControls.CHROMIUM_MILESTONES[milestone + 1];
    const minRevision = ReportControls.CHROMIUM_MILESTONES[milestone];
    return {
      ...state,
      minRevision,
      maxRevision,
      minRevisionInput: minRevision,
      maxRevisionInput: maxRevision,
      milestone,
    };
  },

  receiveSourceOptions: (state, {reportNames}, rootState) => {
    const options = OptionGroup.groupValues(reportNames);
    if (isDebug() || rootState.userEmail) {
      options.push(ReportControls.CREATE);
    }
    const label = `Reports (${reportNames.length})`;
    return {...state, source: {...state.source, options, label}};
  },
};

ElementBase.register(ReportControls);
