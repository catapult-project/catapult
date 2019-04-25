/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import '/@polymer/polymer/lib/elements/dom-if.js';
import '/@polymer/polymer/lib/elements/dom-repeat.js';
import {PolymerElement, html} from '/@polymer/polymer/polymer-element.js';

export default class ChartLegend extends PolymerElement {
  static get is() { return 'chart-legend'; }

  static get template() {
    return html`
      <style>
        :host {
          display: flex;
          flex-direction: column;
        }
        :host * {
          flex-shrink: 0;
        }
        chart-legend {
          margin-left: 16px;
        }
        .leaf {
          cursor: pointer;
        }
        .leaf:hover {
          background: #eee;
        }
      </style>

      <template is="dom-repeat" items="[[items]]">
        <template is="dom-if" if="[[item.children]]">
          <div class="branch">
            [[item.label]]
          </div>

          <chart-legend items="[[item.children]]">
          </chart-legend>
        </template>

        <template is="dom-if" if="[[!item.children]]">
          <div class="leaf"
              style$="color: [[item.color]];"
              on-mouseover="onLeafMouseOver_"
              on-mouseout="onLeafMouseOut_"
              on-click="onLeafClick_">
            [[item.label]]
          </div>
        </template>
      </template>
    `;
  }

  async onLeafMouseOver_(event) {
    this.dispatchEvent(new CustomEvent('leaf-mouseover', {
      bubbles: true,
      composed: true,
      detail: event.model.item,
    }));
  }

  async onLeafMouseOut_(event) {
    this.dispatchEvent(new CustomEvent('leaf-mouseout', {
      bubbles: true,
      composed: true,
      detail: event.model.item,
    }));
  }

  async onLeafClick_(event) {
    event.stopPropagation();
    this.dispatchEvent(new CustomEvent('leaf-click', {
      bubbles: true,
      composed: true,
      detail: event.model.item,
    }));
  }
}

ChartLegend.properties = {
  items: {type: Array},
};

customElements.define(ChartLegend.is, ChartLegend);
