/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './cp-input.js';
import './cp-switch.js';
import './raised-button.js';
import '@polymer/polymer/lib/elements/dom-if.js';
import '@polymer/polymer/lib/elements/dom-repeat.js';
import ElementBase from './element-base.js';
import {TOGGLE, UPDATE} from './simple-redux.js';
import {get} from '@polymer/polymer/lib/utils/path.js';
import {html} from '@polymer/polymer/polymer-element.js';
import {isElementChildOf} from './utils.js';

export default class TriageExisting extends ElementBase {
  static get is() { return 'triage-existing'; }

  static get properties() {
    return {
      statePath: String,
      bugId: String,
      isOpen: {type: Boolean, reflectToAttribute: true},
      onlyIntersectingBugs: Boolean,
      selectedRange: Object,
      recentPerformanceBugs: Array,
    };
  }

  static buildState(options = {}) {
    const selectedRange = new tr.b.math.Range();
    if (!options.alerts) return selectedRange;
    for (const alert of options.alerts) {
      selectedRange.addValue(alert.startRevision);
      selectedRange.addValue(alert.endRevision);
    }

    return {
      bugId: '',
      isOpen: options.isOpen === true,
      onlyIntersectingBugs: true,
      selectedRange,
    };
  }

  static get template() {
    return html`
      <style>
        :host {
          background: var(--background-color);
          box-shadow: var(--elevation-2);
          color: initial;
          display: none;
          flex-direction: column;
          outline: none;
          padding: 16px;
          position: absolute;
          right: 0;
          z-index: var(--layer-menu);
        }
        :host([is-open]) {
          display: flex;
        }

        #controls {
          align-items: center;
          display: flex;
          margin: 0;
          padding: 0;
        }

        .spacer {
          flex-grow: 1;
        }

        cp-switch {
          margin-right: 16px;
        }

        #table-container {
          max-height: 500px;
          overflow: auto;
          margin: 0;
          padding: 0;
        }

        table {
          border-collapse: collapse;
          line-height: 24px;
          margin: 16px 0;
          width: 100%;
        }

        tbody {
          border-width: 0;
        }

        tbody tr:hover {
          background: #eee;
        }

        .bug_id {
          cursor: pointer;
          outline: none;
          font-weight: bold;
        }

        td:nth-of-type(4) {
          max-width: 500px;
        }
      </style>

      <div id="controls">
        <cp-input
            id="bug_input"
            autofocus
            label="Bug Number"
            value="[[bugId]]"
            on-keyup="onIdKeyup_">
        </cp-input>

        <raised-button
            disabled$="[[!isIdValid_(bugId)]]"
            on-click="onSubmit_">
          Submit
        </raised-button>

        <span class="spacer">&nbsp;</span>

        <cp-switch
            checked="[[onlyIntersectingBugs]]"
            on-change="onToggleOnlyIntersectingBugs_">
          <template is="dom-if" if="[[onlyIntersectingBugs]]">
            Intersecting Bugs Only
          </template>
          <template is="dom-if" if="[[!onlyIntersectingBugs]]">
            All Bugs
          </template>
        </cp-switch>
      </div>

      <div id="table-container">
        <table>
          <thead>
            <tr>
              <th>Bug #</th>
              <th>Status</th>
              <th>Owner</th>
              <th>Summary</th>
            </tr>
          </thead>

          <tbody>
            <template is="dom-repeat" items="[[filterBugs_(
                recentPerformanceBugs, onlyIntersectingBugs, selectedRange)]]"
                as="bug">
              <tr>
                <td class="bug_id"
                    on-click="onRecentPerformanceBugClick_"
                    tabindex="0">
                  [[bug.id]]
                </td>

                <td>[[bug.status]]</td>
                <td>[[bug.owner]]</td>
                <td>[[bug.summary]]</td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    `;
  }

  ready() {
    super.ready();
    this.addEventListener('blur', this.onBlur_.bind(this));
    this.addEventListener('keyup', this.onKeyup_.bind(this));
    this.style.minWidth = (window.innerWidth * 0.6) + 'px';
  }

  stateChanged(rootState) {
    const oldIsOpen = this.isOpen;
    this.set('recentPerformanceBugs', rootState.recentPerformanceBugs);
    super.stateChanged(rootState);

    if (this.isOpen && !oldIsOpen) {
      this.$.bug_input.focus();
    }
  }

  async onKeyup_(event) {
    if (event.key === 'Escape') {
      await this.dispatch('close', this.statePath);
    }
  }

  filterBugs_(recentPerformanceBugs, onlyIntersectingBugs, selectedRange) {
    return TriageExisting.filterBugs(
        recentPerformanceBugs, onlyIntersectingBugs, selectedRange);
  }

  isIdValid_(bugId) {
    return bugId && bugId.match(/^\d+$/) !== null;
  }

  async onSubmit_(event) {
    await this.dispatch('close', this.statePath);
    this.dispatchEvent(new CustomEvent('submit', {
      bubbles: true,
      composed: true,
    }));
  }

  async onBlur_(event) {
    if (event.relatedTarget === this ||
        isElementChildOf(event.relatedTarget, this)) {
      this.$.bug_input.focus();
      return;
    }
    await this.dispatch('close', this.statePath);
  }

  async onToggleOnlyIntersectingBugs_(event) {
    await this.dispatch('toggleOnlyIntersectingBugs', this.statePath);
  }

  async onRecentPerformanceBugClick_(event) {
    await this.dispatch('recentPerformanceBug', this.statePath,
        event.model.bug.id);
    this.$.bug_input.focus();
  }

  async onIdKeyup_(event) {
    if (event.key === 'Enter' && this.isIdValid_(this.bugId)) {
      this.onSubmit_(event);
      return;
    }
    await this.dispatch('recentPerformanceBug', this.statePath,
        event.target.value);
  }
}

TriageExisting.actions = {
  toggleOnlyIntersectingBugs: statePath => async(dispatch, getState) => {
    dispatch(TOGGLE(`${statePath}.onlyIntersectingBugs`));
  },

  recentPerformanceBug: (statePath, bugId) => async(dispatch, getState) => {
    dispatch(UPDATE(statePath, {bugId}));
  },

  close: statePath => async(dispatch, getState) => {
    dispatch(UPDATE(statePath, {isOpen: false}));
  },
};

TriageExisting.filterBugs =
  (recentPerformanceBugs, onlyIntersectingBugs, selectedRange) => {
    if (!recentPerformanceBugs || !selectedRange) return [];
    if (!onlyIntersectingBugs) return recentPerformanceBugs;
    return recentPerformanceBugs.filter(bug =>
      bug.revisionRange.intersectsRangeInclusive(selectedRange));
  };

ElementBase.register(TriageExisting);
