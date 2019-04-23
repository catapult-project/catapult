/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './cp-input.js';
import './raised-button.js';
import ElementBase from './element-base.js';
import MenuInput from './menu-input.js';
import OptionGroup from './option-group.js';
import ReportNamesRequest from './report-names-request.js';
import {UPDATE} from './simple-redux.js';

import {
  buildProperties,
  buildState,
  simpleGUID,
} from './utils.js';

export default class ReportControls extends ElementBase {
  static get is() { return 'report-controls'; }

  static get template() {
    return Polymer.html`
      <style>
        :host {
          display: flex;
          align-items: center;
        }

        #source {
          width: 250px;
        }

        #prev_mstone,
        #next_mstone {
          font-size: larger;
        }

        #alerts {
          color: var(--primary-color-dark);
        }

        #min_revision {
          margin-right: 8px;
        }

        #min_revision,
        #max_revision {
          width: 84px;
        }

        #close {
          align-self: flex-start;
          cursor: pointer;
          flex-shrink: 0;
          height: var(--icon-size, 1em);
          width: var(--icon-size, 1em);
        }

        .spacer {
          flex-grow: 1;
        }
      </style>

      <menu-input id="source" state-path="[[statePath]].source"></menu-input>

      <raised-button
          id="alerts"
          title="Alerts"
          on-click="onAlerts_">
        <iron-icon icon="cp:alert">
        </iron-icon>
        <span class="nav_button_label">
          Alerts
        </span>
      </raised-button>

      <span class="spacer">&nbsp;</span>

      <raised-button
          id="prev_mstone"
          disabled$="[[!isPreviousMilestone_(milestone)]]"
          on-click="onPreviousMilestone_">
        [[prevMstoneButtonLabel_(milestone, maxRevision)]]
        <iron-icon icon="cp:left"></iron-icon>
      </raised-button>

      <cp-input
          id="min_revision"
          value="[[minRevisionInput]]"
          label="Min Revision"
          on-keyup="onMinRevisionKeyup_">
      </cp-input>

      <cp-input
          id="max_revision"
          value="[[maxRevisionInput]]"
          label="Max Revision"
          on-keyup="onMaxRevisionKeyup_">
      </cp-input>

      <raised-button
          id="next_mstone"
          disabled$="[[!isNextMilestone_(milestone)]]"
          on-click="onNextMilestone_">
        <iron-icon icon="cp:right"></iron-icon>
        M[[add_(milestone, 1)]]
      </raised-button>

      <span class="spacer">&nbsp;</span>

      <iron-icon id="close" icon="cp:close" on-click="onCloseSection_">
      </iron-icon>
    `;
  }

  connectedCallback() {
    super.connectedCallback();
    this.dispatch('connected', this.statePath);
  }

  async onCloseSection_() {
    await this.dispatchEvent(new CustomEvent('close-section', {
      bubbles: true,
      composed: true,
      detail: {sectionId: this.sectionId},
    }));
  }

  prevMstoneButtonLabel_(milestone, maxRevision) {
    return this.prevMstoneLabel_(milestone - 1, maxRevision);
  }

  prevMstoneLabel_(milestone, maxRevision) {
    if (maxRevision === 'latest') milestone += 1;
    return `M${milestone - 1}`;
  }

  async onPreviousMilestone_() {
    await this.dispatch('selectMilestone', this.statePath,
        this.milestone - 1);
  }

  async onNextMilestone_() {
    await this.dispatch('selectMilestone', this.statePath,
        this.milestone + 1);
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
    await this.dispatch('setMinRevision', this.statePath, event.target.value);
  }

  async onMaxRevisionKeyup_(event) {
    await this.dispatch('setMaxRevision', this.statePath, event.target.value);
  }

  isPreviousMilestone_(milestone) {
    return milestone > (MIN_MILESTONE + 1);
  }

  isNextMilestone_(milestone) {
    return milestone < ReportControls.CURRENT_MILESTONE;
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

ReportControls.CURRENT_MILESTONE = tr.b.math.Statistics.max(
    Object.keys(ReportControls.CHROMIUM_MILESTONES));
const MIN_MILESTONE = tr.b.math.Statistics.min(
    Object.keys(ReportControls.CHROMIUM_MILESTONES));

ReportControls.State = {
  milestone: options => parseInt(options.milestone) ||
    ReportControls.CURRENT_MILESTONE,
  minRevision: options => options.minRevision,
  maxRevision: options => options.maxRevision,
  minRevisionInput: options => options.minRevision,
  maxRevisionInput: options => options.maxRevision,
  sectionId: options => options.sectionId || simpleGUID(),
  source: options => MenuInput.buildState({
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

ReportControls.buildState = options => buildState(
    ReportControls.State, options);

ReportControls.properties = {
  ...buildProperties('state', ReportControls.State),
  userEmail: {statePath: 'userEmail'},
};
ReportControls.observers = [
];

ReportControls.DEFAULT_NAME = 'Chromium Performance Overview';
ReportControls.CREATE = '[Create new report]';

ReportControls.actions = {
  connected: statePath => async(dispatch, getState) => {
    await ReportControls.actions.loadSources(statePath)(dispatch, getState);

    let state = Polymer.Path.get(getState(), statePath);
    if (state.minRevision === undefined ||
        state.maxRevision === undefined) {
      ReportControls.actions.selectMilestone(
          statePath, state.milestone)(dispatch, getState);
      state = Polymer.Path.get(getState(), statePath);
    }

    if (state.source.selectedOptions.length === 0) {
      MenuInput.actions.focus(
          statePath + '.source')(dispatch, getState);
    }
  },

  selectMilestone: (statePath, milestone) => async(dispatch, getState) => {
    dispatch({
      type: ReportControls.reducers.selectMilestone.name,
      statePath,
      milestone,
    });
  },

  loadSources: statePath => async(dispatch, getState) => {
    const reportTemplateInfos = await new ReportNamesRequest().response;
    const reportNames = reportTemplateInfos.map(t => t.name);
    dispatch({
      type: ReportControls.reducers.receiveSourceOptions.name,
      statePath,
      reportNames,
    });
  },

  setMinRevision: (statePath, minRevisionInput) =>
    async(dispatch, getState) => {
      dispatch(UPDATE(statePath, {minRevisionInput}));
      if (!minRevisionInput.match(/^\d{6}$/)) return;
      dispatch(UPDATE(statePath, {minRevision: minRevisionInput}));
    },

  setMaxRevision: (statePath, maxRevisionInput) =>
    async(dispatch, getState) => {
      dispatch(UPDATE(statePath, {maxRevisionInput}));
      if (!maxRevisionInput.match(/^\d{6}$/)) return;
      dispatch(UPDATE(statePath, {maxRevision: maxRevisionInput}));
    },
};

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
    if (window.IS_DEBUG || rootState.userEmail) {
      options.push(ReportControls.CREATE);
    }
    const label = `Reports (${reportNames.length})`;
    return {...state, source: {...state.source, options, label}};
  },
};

ElementBase.register(ReportControls);
