/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './cp-input.js';
import './cp-loading.js';
import './cp-radio-group.js';
import './cp-radio.js';
import './error-set.js';
import './raised-button.js';
import '@polymer/polymer/lib/elements/dom-if.js';
import ElementBase from './element-base.js';
import NewPinpointRequest from './new-pinpoint-request.js';
import {UPDATE} from './simple-redux.js';
import {html} from '@polymer/polymer/polymer-element.js';
import {isElementChildOf, pinpointJob} from './utils.js';

// Display a warning when bisecting large revision ranges.
const MANY_REVISIONS = 100;

export default class BisectDialog extends ElementBase {
  static get is() { return 'bisect-dialog'; }

  static get properties() {
    return {
      statePath: String,

      alertKeys: Array,
      able: Boolean,
      tooltip: String,
      errors: Array,
      isLoading: Boolean,
      isOpen: Boolean,
      jobId: String,
      bugId: String,
      patch: String,
      suite: String,
      measurement: String,
      bot: String,
      case: String,
      statistic: String,
      mode: String,
      startRevision: Number,
      endRevision: Number,
    };
  }

  static buildState(options = {}) {
    return {
      alertKeys: options.alertKeys || [],
      able: options.able || true,
      tooltip: options.tooltip || '',
      errors: [],
      isLoading: false,
      isOpen: false,
      jobId: '',
      bugId: options.bugId || '',
      patch: options.patch || '',
      suite: options.suite || '',
      measurement: options.measurement || '',
      bot: options.bot || '',
      case: options.case || '',
      statistic: options.statistic || '',
      mode: options.mode || BisectDialog.MODE.PERFORMANCE,
      startRevision: options.startRevision || 0,
      endRevision: options.endRevision || 0,
    };
  }

  static get template() {
    return html`
      <style>
        :host {
          position: relative;
        }

        #dialog {
          background: var(--background-color, white);
          box-shadow: var(--elevation-2);
          flex-direction: column;
          outline: none;
          padding: 16px;
          position: absolute;
          bottom: 0;
          z-index: var(--layer-menu, 100);
        }
        cp-input {
          margin: 12px 4px 4px 4px;
          width: 100px;
        }
        cp-radio-group {
          margin-left: 8px;
          flex-direction: row;
        }
        .row raised-button {
          flex-grow: 1;
        }
        .row {
          display: flex;
          align-items: center;
        }
        .warning {
          color: var(--error-color, red);
        }
        #cancel {
          background: var(--background-color, white);
          box-shadow: none;
        }
      </style>

      <raised-button
          id="open"
          disabled$="[[!able]]"
          title$="[[tooltip]]"
          on-click="onOpen_">
        Bisect [[startRevision]] - [[endRevision]]
      </raised-button>

      <error-set errors="[[errors]]"></error-set>
      <cp-loading loading$="[[isLoading]]">
      </cp-loading>
      <template is="dom-if" if="[[jobId]]">
        <a target="_blank" href="[[pinpoint_(jobId)]]">[[jobId]]</a>
      </template>

      <div id="dialog" hidden$="[[!isOpen]]">
        <table>
          <tr>
            <td>Suite</td>
            <td>[[suite]]</td>
          </tr>
          <tr>
            <td>Bot</td>
            <td>[[bot]]</td>
          </tr>
          <tr>
            <td>Measurement</td>
            <td>[[measurement]]</td>
          </tr>
          <template is="dom-if" if="[[case]]">
            <tr>
              <td>Case</td>
              <td>[[case]]</td>
            </tr>
          </template>
          <template is="dom-if" if="[[statistic]]">
            <tr>
              <td>Statistic</td>
              <td>[[statistic]]</td>
            </tr>
          </template>
        </table>

        <div class="row">
          <cp-input
              id="start_revision"
              label="Start Revision"
              tabindex="0"
              value="[[startRevision]]"
              on-change="onStartRevision_">
          </cp-input>

          <cp-input
              id="end_revision"
              label="End Revision"
              tabindex="0"
              value="[[endRevision]]"
              on-change="onEndRevision_">
          </cp-input>
        </div>

        <div class="row">
          <cp-input
              id="bug_id"
              label="Bug ID"
              tabindex="0"
              value="[[bugId]]"
              on-change="onBugId_">
          </cp-input>

          <cp-input
              id="patch"
              label="Patch"
              title="optional patch to apply to the entire job"
              tabindex="0"
              value="[[patch]]"
              on-change="onPatch_">
          </cp-input>
        </div>

        <div class="row">
          Mode:
          <cp-radio-group
              id="mode"
              selected="[[mode]]"
              on-selected-changed="onModeChange_">
            <cp-radio name="performance">
              Performance
            </cp-radio>
            <cp-radio name="functional">
              Functional
            </cp-radio>
          </cp-radio-group>
        </div>

        <template is="dom-if"
            if="[[isRangeLarge_(startRevision, endRevision)]]">
          <div class="row warning">
            Warning: bisect large revision ranges is slow and expensive.
          </div>
        </template>

        <div class="row">
          <raised-button
              id="cancel"
              on-click="onCancel_"
              tabindex="0">
            Cancel
          </raised-button>
          <raised-button
              id="start"
              on-click="onSubmit_"
              tabindex="0">
            Start
          </raised-button>
        </div>
      </div>
    `;
  }

  ready() {
    super.ready();
    this.addEventListener('blur', this.onBlur_.bind(this));
    this.addEventListener('keyup', this.onKeyup_.bind(this));
  }

  stateChanged(rootState) {
    super.stateChanged(rootState);

    if (this.isOpen) {
      this.$.cancel.focus();
    }
  }

  isRangeLarge_(startRevision, endRevision) {
    return (endRevision - startRevision) > MANY_REVISIONS;
  }

  pinpoint_(jobId) {
    return pinpointJob(jobId);
  }

  async onKeyup_(event) {
    if (event.key === 'Escape') {
      await this.dispatch(UPDATE(this.statePath, {isOpen: false}));
    }
  }

  async onBlur_(event) {
    if (event.relatedTarget === this ||
        isElementChildOf(event.relatedTarget, this)) {
      return;
    }
    await this.dispatch(UPDATE(this.statePath, {isOpen: false}));
  }

  async onCancel_(event) {
    await this.dispatch(UPDATE(this.statePath, {isOpen: false}));
  }

  async onStartRevision_(event) {
    await this.dispatch(UPDATE(this.statePath, {
      startRevision: event.detail.value,
    }));
  }

  async onEndRevision_(event) {
    await this.dispatch(UPDATE(this.statePath, {
      endRevision: event.detail.value,
    }));
  }

  async onBugId_(event) {
    await this.dispatch(UPDATE(this.statePath, {bugId: event.detail.value}));
  }

  async onModeChange_(event) {
    if (!event.detail.value) return;
    await this.dispatch(UPDATE(this.statePath, {mode: event.detail.value}));
  }

  async onPatch_(event) {
    await this.dispatch(UPDATE(this.statePath, {patch: event.detail.value}));
  }

  async onOpen_(event) {
    await this.dispatch(UPDATE(this.statePath, {isOpen: true}));
  }

  async onSubmit_(event) {
    try {
      this.dispatch(UPDATE(this.statePath, {isOpen: false, isLoading: true}));
      const request = new NewPinpointRequest({
        alerts: this.alertKeys,
        suite: this.suite,
        bot: this.bot,
        measurement: this.measurement,
        case: this.case,
        statistic: this.statistic,
        mode: this.mode,
        bugId: this.bugId,
        patch: this.patch,
        startRevision: this.startRevision,
        endRevision: this.endRevision,
      });
      const jobId = await request.response;
      this.dispatch(UPDATE(this.statePath, {isLoading: false, jobId}));
    } catch (err) {
      this.dispatch(UPDATE(this.statePath, {
        isLoading: false,
        errors: [err.message],
      }));
    }
  }
}

BisectDialog.MODE = {
  PERFORMANCE: 'performance',
  FUNCTIONAL: 'functional',
};

ElementBase.register(BisectDialog);
