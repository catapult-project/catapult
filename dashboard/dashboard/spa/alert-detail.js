/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './cp-icon.js';
import './cp-loading.js';
import './error-set.js';
import ExistingBugRequest from './existing-bug-request.js';
import NewBugRequest from './new-bug-request.js';
import NudgeAlert from './nudge-alert.js';
import TriageExisting from './triage-existing.js';
import TriageNew from './triage-new.js';
import {ElementBase, STORE} from './element-base.js';
import {TOGGLE, UPDATE} from './simple-redux.js';
import {html, css} from 'lit-element';

import {
  buildProperties,
  buildState,
  crbug,
  get,
  isProduction,
  pinpointJob,
} from './utils.js';

export default class AlertDetail extends ElementBase {
  static get is() { return 'alert-detail'; }

  static get properties() {
    return {
      statePath: String,

      bugId: Number,
      deltaUnit: Object,
      deltaValue: Number,
      endRevision: Number,
      key: String,
      percentDeltaUnit: Object,
      percentDeltaValue: Number,
      startRevision: Number,
      statistic: String,
      pinpointJobs: Array,
      suite: String,
      measurement: String,
      bot: String,
      case: String,
      master: String,
      improvement: Boolean,

      borderColor: String,
      isLoading: Boolean,
      errors: Array,
      newBug: Object,
      existingBug: Object,
      descriptorParts: Array,
    };
  }

  static buildState(options = {}) {
    return {
      bugId: options.bugId || 0,
      deltaUnit: options.deltaUnit || undefined,
      deltaValue: options.deltaValue || 0,
      endRevision: options.endRevision || 0,
      key: options.key || '',
      percentDeltaUnit: options.percentDeltaUnit || undefined,
      percentDeltaValue: options.percentDeltaValue || 0,
      startRevision: options.startRevision || 0,
      statistic: options.statistic || '',
      pinpointJobs: options.pinpointJobs || [],
      suite: options.suite || '',
      measurement: options.measurement || '',
      bot: options.bot || '',
      case: options.case || '',
      master: options.master || '',
      improvement: options.improvement || false,

      isLoading: false,
      errors: [],
      newBug: TriageNew.buildState({}),
      existingBug: TriageExisting.buildState({}),
      descriptorParts: [],
    };
  }

  static get styles() {
    return css`
      :host {
        border-width: 1px;
        border-style: solid;
        display: block;
        padding: 4px;
        margin: 4px;
      }
      #chart-button {
        cursor: pointer;
        color: var(--primary-color-dark, blue);
      }
      table {
        width: 100%;
      }
      flex {
        display: flex;
      }
      flex * {
        flex-grow: 1;
      }
      flex[hidden] {
        display: none;
      }
      #start-revision {
        margin-right: 8px;
      }
      td:first-child {
        border-right: 8px solid var(--background-color, white);
      }
    `;
  }

  render() {
    let bugLink = '';
    if (this.bugId < 0) {
      bugLink = 'Ignored';
    } else if (this.bugId > 0) {
      bugLink = html`
        <a href="${crbug(this.bugId)}" target="_blank">${this.bugId}</a>
      `;
    }

    return html`
      <div id="chart-button"
          ?hidden="${!this.descriptorParts.length}"
          @click="${this.onNewChart_}">
        <cp-icon icon="chart"></cp-icon>
        ${(this.descriptorParts || []).map(part => html`<span>${part}</span>`)}
      </div>

      <table>
        <tr>
          <td>
            ${this.startRevision}-${this.endRevision}
          </td>
          <td>&#916;${this.statistic || 'avg'}</td>
          <td>
            <scalar-span
                .value="${this.deltaValue}"
                .unit="${this.deltaUnit}">
            </scalar-span>
          </td>
        </tr>

        <tr>
          <td>
            ${bugLink}
          </td>
          <td>%&#916;${this.statistic || 'avg'}</td>
          <td>
            <scalar-span
                .value="${this.percentDeltaValue}"
                .unit="${this.percentDeltaUnit}"
                .maximumFractionDigits="1">
            </scalar-span>
          </td>
        </tr>
      </table>

      <error-set .errors="${this.errors}"></error-set>
      <cp-loading ?loading="${this.isLoading}"></cp-loading>

      ${(!this.pinpointJobs || !this.pinpointJobs.length) ? '' : html`
        Pinpoint jobs:
      `}
      ${(this.pinpointJobs || []).map(jobId => html`
        <a target="_blank" href="${pinpointJob(this.jobId)}">${jobId}</a>
      `)}

      <flex ?hidden="${!isProduction()}">
        <span style="position: relative;">
          <raised-button @click="${this.onNudge_}">
            Nudge
          </raised-button>
          <nudge-alert
              .statePath="${this.statePath}.nudge"
              tabindex="0">
          </nudge-alert>
        </span>

        ${this.bugId ? html`
          <raised-button @click="${this.onUnassign_}">
            Unassign
          </raised-button>
        ` : html`
          <span style="position: relative;">
            <raised-button id="new" @click="${this.onTriageNew_}">
              New Bug
            </raised-button>
            <triage-new
                tabindex="0"
                .statePath="${this.statePath}.newBug"
                @submit="${this.onTriageNewSubmit_}">
            </triage-new>
          </span>

          <span style="position: relative;">
            <raised-button id="existing" @click="${this.onTriageExisting_}">
              Existing Bug
            </raised-button>

            <triage-existing
                tabindex="0"
                .statePath="${this.statePath}.existingBug"
                @submit="${this.onTriageExistingSubmit_}">
            </triage-existing>
          </span>

          <raised-button id="ignore" @click="${this.onIgnore_}">
            Ignore
          </raised-button>
        `}
      </flex>
    `;
  }

  stateChanged(rootState) {
    super.stateChanged(rootState);
    if (this.improvement) {
      this.style.borderColor = 'var(--improvement-color, green)';
    } else if (this.bugId) {
      this.style.borderColor = 'var(--neutral-color-dark, grey)';
    } else {
      this.style.borderColor = 'var(--error-color, red)';
    }
  }

  async onNewChart_(event) {
    this.dispatchEvent(new CustomEvent('new-chart', {
      bubbles: true,
      composed: true,
      detail: {
        options: {
          parameters: {
            suites: [this.suite],
            measurements: [this.measurement],
            bots: [this.master + ':' + this.bot],
            cases: this.case ? [this.case] : [],
          },
        },
      },
    }));
  }

  async onTriageNew_() {
    this.dispatchEvent(new CustomEvent('require-sign-in', {
      bubbles: true,
      composed: true,
    }));
    STORE.dispatch({
      type: AlertDetail.reducers.triageNew.name,
      statePath: this.statePath,
    });
  }

  async onTriageExisting_() {
    this.dispatchEvent(new CustomEvent('require-sign-in', {
      bubbles: true,
      composed: true,
    }));
    STORE.dispatch({
      type: AlertDetail.reducers.triageExisting.name,
      statePath: this.statePath,
    });
  }

  async onTriageNewSubmit_() {
    await AlertDetail.submitNewBug(this.statePath);
  }

  static async submitNewBug(statePath) {
    STORE.dispatch(UPDATE(statePath, {
      bugId: '[creating]',
      newBug: TriageNew.buildState({}),
    }));

    const state = get(STORE.getState(), statePath);
    try {
      const request = new NewBugRequest({
        alertKeys: [state.key],
        ...state.newBug,
        labels: state.newBug.labels.filter(
            x => x.isEnabled).map(x => x.name),
        components: state.newBug.components.filter(
            x => x.isEnabled).map(x => x.name),
      });
      const bugId = await request.response;
      STORE.dispatch(UPDATE(statePath, {bugId}));
    } catch (err) {
      STORE.dispatch(UPDATE(statePath, {errors: [err.message]}));
    }
    STORE.dispatch(UPDATE(statePath, {isLoading: false}));
  }

  async onNudge_() {
    this.dispatchEvent(new CustomEvent('require-sign-in', {
      bubbles: true,
      composed: true,
    }));
    await STORE.dispatch(UPDATE(this.statePath + '.nudge', {isOpen: true}));
  }

  async onUnassign_() {
    this.dispatchEvent(new CustomEvent('require-sign-in', {
      bubbles: true,
      composed: true,
    }));
    await AlertDetail.changeBugId(this.statePath, 0);
  }

  async onTriageExistingSubmit_() {
    STORE.dispatch(UPDATE(this.statePath + '.existingBug', {isOpen: false}));
    await AlertDetail.changeBugId(this.statePath, this.existingBug.bugId);
  }

  async onIgnore_() {
    this.dispatchEvent(new CustomEvent('require-sign-in', {
      bubbles: true,
      composed: true,
    }));
    await AlertDetail.changeBugId(this.statePath, -2);
  }

  static async changeBugId(statePath, bugId) {
    // Assume success.
    STORE.dispatch(UPDATE(statePath, {bugId, isLoading: true}));
    const alertKeys = [get(STORE.getState(), statePath).key];
    try {
      const request = new ExistingBugRequest({alertKeys, bugId});
      await request.response;
    } catch (err) {
      STORE.dispatch(UPDATE(statePath, {errors: [err.message]}));
    }
    STORE.dispatch(UPDATE(statePath, {isLoading: false}));
  }
}

AlertDetail.reducers = {
  triageNew: (state, action, rootState) => {
    const newBug = TriageNew.buildState({
      isOpen: true,
      alerts: [state],
      cc: rootState.userEmail,
    });
    return {...state, newBug};
  },

  triageExisting: (state, action, rootState) => {
    const existingBug = TriageExisting.buildState({
      isOpen: true,
      alerts: [state],
    });
    return {...state, existingBug};
  },
};

ElementBase.register(AlertDetail);
