/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {LitElement, html, css} from 'lit-element';

export default class ScalarSpan extends LitElement {
  static get is() { return 'scalar-span'; }

  static get properties() {
    return {
      maximumFractionDigits: {type: Number},
      unit: {type: Object},
      unitPrefix: {type: Object},
      value: {type: Number},
    };
  }

  static get styles() {
    return css`
      :host {
        display: flex;
        flex-direction: row;
        justify-content: flex-end;
        white-space: nowrap;
      }
      span[change="improvement"] {
        color: var(--improvement-color, green)
      }
      span[change="regression"] {
        color: var(--error-color, red);
      }
    `;
  }

  static getChange(unit, value) {
    if (!unit) return '';
    if (!unit.isDelta) return '';
    if (unit.improvementDirection === tr.b.ImprovementDirection.DONT_CARE) {
      return '';
    }
    if (value === 0) return '';
    if (unit.improvementDirection ===
        tr.b.ImprovementDirection.BIGGER_IS_BETTER) {
      return value > 0 ? 'improvement' : 'regression';
    }
    return value < 0 ? 'improvement' : 'regression';
  }

  render() {
    const change = ScalarSpan.getChange(this.unit, this.value);
    const formatted = !this.unit ? this.value : this.unit.format(this.value, {
      maximumFractionDigits: this.maximumFractionDigits,
      unitPrefix: this.unitPrefix,
    });
    return html`
      <span id="span"
          change="${change}"
          title="${change}">
        ${formatted}
      </span>
    `;
  }

  firstUpdated() {
    this.span = this.shadowRoot.querySelector('#span');
  }
}

customElements.define(ScalarSpan.is, ScalarSpan);
