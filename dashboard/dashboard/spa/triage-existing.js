/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './cp-flex.js';
import '@chopsui/chops-button';
import '@chopsui/chops-input';
import '@chopsui/chops-switch';
import {ElementBase, STORE} from './element-base.js';
import {TOGGLE, UPDATE} from './simple-redux.js';
import {get} from 'dot-prop-immutable';
import {html, css} from 'lit-element';
import {measureElement, isElementChildOf} from './utils.js';

export class TriageExisting extends ElementBase {
  static get is() { return 'triage-existing'; }

  static get properties() {
    return {
      statePath: String,
      bugId: String,
      isOpen: {type: Boolean, reflect: true},
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

  static get styles() {
    return css`
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
      :host([isopen]) {
        display: flex;
      }

      #controls {
        align-items: center;
        margin: 0;
        min-width: 400px;
        padding: 0;
      }

      .spacer {
        flex-grow: 1;
      }

      chops-switch {
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
        min-width: 400px;
      }
    `;
  }

  render() {
    const switchTitle = this.onlyIntersectingBugs ? `Now only showing
    intersecting bugs. Click to switch to show all bugs.` : `Now showing all
    bugs. Click to switch to only show intersecting bugs.`;
    const filteredBugs = TriageExisting.filterBugs(
        this.recentPerformanceBugs,
        this.onlyIntersectingBugs,
        this.selectedRange);

    return html`
      <cp-flex id="controls">
        <chops-input
            id="bug_input"
            autofocus
            label="Bug Number"
            .value="${this.bugId}"
            @keyup="${this.onIdKeyup_}">
        </chops-input>

        <chops-button
            ?disabled="${!this.isIdValid_(this.bugId)}"
            @click="${this.onSubmit_}">
          Submit
        </chops-button>

        <span class="spacer">&nbsp;</span>

        <chops-switch
            ?checked="${this.onlyIntersectingBugs}"
            title="${switchTitle}"
            @change="${this.onToggleOnlyIntersectingBugs_}">
          Intersecting Bugs Only
        </chops-switch>
      </cp-flex>

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
            ${filteredBugs.map(bug => html`
              <tr>
                <td class="bug_id"
                    @click="${event =>
    this.onRecentPerformanceBugClick_(bug.id)}"
                    tabindex="0">
                  ${bug.id}
                </td>

                <td>${bug.status}</td>
                <td>${bug.owner}</td>
                <td>${bug.summary}</td>
              </tr>
            `)}
          </tbody>
        </table>
      </div>
    `;
  }

  constructor() {
    super();
    this.addEventListener('blur', this.onBlur_.bind(this));
    this.addEventListener('keyup', this.onKeyup_.bind(this));
  }

  async stateChanged(rootState) {
    const oldIsOpen = this.isOpen;
    this.recentPerformanceBugs = rootState.recentPerformanceBugs;
    super.stateChanged(rootState);

    if (this.isOpen && !oldIsOpen) {
      const rect = await measureElement(this);
      // The drawer is about 33px. There's 32px of padding in this dialog.
      this.style.maxWidth = (rect.right - 33 - 32) + 'px';

      this.shadowRoot.querySelector('#bug_input').focus();
    }
  }

  async onKeyup_(event) {
    if (event.key === 'Escape') {
      await STORE.dispatch(UPDATE(this.statePath, {isOpen: false}));
    }
  }

  isIdValid_(bugId) {
    return bugId && bugId.match(/^\d+$/) !== null;
  }

  async onSubmit_(event) {
    await STORE.dispatch(UPDATE(this.statePath, {isOpen: false}));
    this.dispatchEvent(new CustomEvent('submit', {
      bubbles: true,
      composed: true,
    }));
  }

  async onBlur_(event) {
    if (event.relatedTarget === this ||
        isElementChildOf(event.relatedTarget, this)) {
      this.shadowRoot.querySelector('#bug_input').focus();
      return;
    }
    await STORE.dispatch(UPDATE(this.statePath, {isOpen: false}));
  }

  async onToggleOnlyIntersectingBugs_(event) {
    await STORE.dispatch(TOGGLE(this.statePath + '.onlyIntersectingBugs'));
  }

  async onRecentPerformanceBugClick_(bugId) {
    await STORE.dispatch(UPDATE(this.statePath, {bugId}));
    this.shadowRoot.querySelector('#bug_input').focus();
  }

  async onIdKeyup_(event) {
    if (event.key === 'Enter' && this.isIdValid_(this.bugId)) {
      this.onSubmit_(event);
      return;
    }
    await STORE.dispatch(UPDATE(this.statePath, {bugId: event.target.value}));
  }

  static filterBugs(
      recentPerformanceBugs, onlyIntersectingBugs, selectedRange) {
    if (!recentPerformanceBugs || !selectedRange) return [];
    if (!onlyIntersectingBugs) return recentPerformanceBugs;
    return recentPerformanceBugs.filter(bug =>
      bug.revisionRange.intersectsRangeInclusive(selectedRange));
  }
}

ElementBase.register(TriageExisting);
