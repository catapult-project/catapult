/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './cp-loading.js';
import './error-set.js';
import '@polymer/polymer/lib/elements/dom-if.js';
import '@polymer/polymer/lib/elements/dom-repeat.js';
import ElementBase from './element-base.js';
import ExistingBugRequest from './existing-bug-request.js';
import NewBugRequest from './new-bug-request.js';
import NudgeAlert from './nudge-alert.js';
import TriageExisting from './triage-existing.js';
import TriageNew from './triage-new.js';
import {TOGGLE, UPDATE} from './simple-redux.js';
import {get} from '@polymer/polymer/lib/utils/path.js';
import {html} from '@polymer/polymer/polymer-element.js';

import {
  buildProperties,
  buildState,
  crbug,
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

  static get template() {
    return html`
      <style>
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
        #start-revision {
          margin-right: 8px;
        }
        td:first-child {
          border-right: 8px solid var(--background-color, white);
        }
      </style>

      <div id="chart-button"
          hidden$="[[isEmpty_(descriptorParts)]]"
          on-click="onNewChart_">
        <iron-icon icon="cp:chart"></iron-icon>
        <template is="dom-repeat" items="[[descriptorParts]]" as="part">
          <span>[[part]]</span>
        </template>
      </div>

      <table>
        <tr>
          <td>
            [[startRevision]]-[[endRevision]]
          </td>
          <td>&#916;[[default_(statistic, 'avg')]]</td>
          <td>
            <scalar-span
                value="[[deltaValue]]"
                unit="[[deltaUnit]]">
            </scalar-span>
          </td>
        </tr>

        <tr>
          <td>
            <template is="dom-if" if="[[bugId]]">
              <template is="dom-if" if="[[isValidBugId_(bugId)]]">
                <a href="[[crbug_(bugId)]]" target="_blank">[[bugId]]</a>
              </template>

              <template is="dom-if" if="[[isInvalidBugId_(bugId)]]">
                Ignored
              </template>
            </template>
          </td>
          <td>%&#916;[[default_(statistic, 'avg')]]</td>
          <td>
            <scalar-span
                value="[[percentDeltaValue]]"
                unit="[[percentDeltaUnit]]"
                maximum-fraction-digits="1">
            </scalar-span>
          </td>
        </tr>
      </table>

      <error-set errors="[[errors]]"></error-set>
      <cp-loading loading$="[[isLoading]]"></cp-loading>

      <template is="dom-if" if="[[!isEmpty_(pinpointJobs)]]">
        Pinpoint jobs:
      </template>
      <template is="dom-repeat" items="[[pinpointJobs]]" as="jobId">
        <a target="_blank" href="[[pinpoint_(jobId)]]">[[jobId]]</a>
      </template>

      <flex>
        <span style="position: relative;">
          <raised-button on-click="onNudge_">
            Nudge
          </raised-button>
          <nudge-alert
              state-path="[[statePath]].nudge"
              tabindex="0">
          </nudge-alert>
        </span>

        <template is="dom-if" if="[[bugId]]">
          <raised-button on-click="onUnassign_">
            Unassign
          </raised-button>
        </template>

        <template is="dom-if" if="[[!bugId]]">
          <span style="position: relative;">
            <raised-button id="new" on-click="onTriageNew_">
              New Bug
            </raised-button>
            <triage-new
                tabindex="0"
                state-path="[[statePath]].newBug"
                on-submit="onTriageNewSubmit_">
            </triage-new>
          </span>

          <span style="position: relative;">
            <raised-button id="existing" on-click="onTriageExisting_">
              Existing Bug
            </raised-button>

            <triage-existing
                tabindex="0"
                state-path="[[statePath]].existingBug"
                on-submit="onTriageExistingSubmit_">
            </triage-existing>
          </span>

          <raised-button id="ignore" on-click="onIgnore_">
            Ignore
          </raised-button>
        </template>
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

  pinpoint_(jobId) {
    return pinpointJob(jobId);
  }

  isValidBugId_(bugId) {
    return bugId > 0;
  }

  isInvalidBugId_(bugId) {
    return bugId < 0;
  }

  crbug_(bugId) {
    return crbug(bugId);
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
    this.dispatch({
      type: AlertDetail.reducers.triageNew.name,
      statePath: this.statePath,
    });
  }

  async onTriageExisting_() {
    this.dispatchEvent(new CustomEvent('require-sign-in', {
      bubbles: true,
      composed: true,
    }));
    this.dispatch({
      type: AlertDetail.reducers.triageExisting.name,
      statePath: this.statePath,
    });
  }

  async onTriageNewSubmit_() {
    await this.dispatch('submitNewBug', this.statePath);
  }

  async onNudge_() {
    this.dispatchEvent(new CustomEvent('require-sign-in', {
      bubbles: true,
      composed: true,
    }));
    await this.dispatch(UPDATE(this.statePath + '.nudge', {isOpen: true}));
  }

  async onUnassign_() {
    this.dispatchEvent(new CustomEvent('require-sign-in', {
      bubbles: true,
      composed: true,
    }));
    await this.dispatch('changeBugId', this.statePath, 0);
  }

  async onTriageExistingSubmit_() {
    this.dispatch(UPDATE(this.statePath + '.existingBug', {isOpen: false}));
    await this.dispatch('changeBugId', this.statePath, this.existingBug.bugId);
  }

  async onIgnore_() {
    this.dispatchEvent(new CustomEvent('require-sign-in', {
      bubbles: true,
      composed: true,
    }));
    await this.dispatch('changeBugId', this.statePath, -2);
  }
}

AlertDetail.actions = {
  changeBugId: (statePath, bugId) => async(dispatch, getState) => {
    // Assume success.
    dispatch(UPDATE(statePath, {bugId, isLoading: true}));
    const alertKeys = [get(getState(), statePath).key];
    try {
      const request = new ExistingBugRequest({alertKeys, bugId});
      await request.response;
    } catch (err) {
      dispatch(UPDATE(statePath, {errors: [err.message]}));
    }
    dispatch(UPDATE(statePath, {isLoading: false}));
  },

  submitNewBug: statePath => async(dispatch, getState) => {
    dispatch(UPDATE(statePath, {
      bugId: '[creating]',
      newBug: TriageNew.buildState({}),
    }));

    const state = get(getState(), statePath);
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
      dispatch(UPDATE(statePath, {bugId}));
      // TODO storeRecentlyModifiedBugs
    } catch (err) {
      dispatch(UPDATE(statePath, {errors: [err.message]}));
    }
    dispatch(UPDATE(statePath, {isLoading: false}));
  },
};

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
