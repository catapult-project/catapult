/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {PolymerElement, html} from '@polymer/polymer/polymer-element.js';

export default class ColumnHead extends PolymerElement {
  static get is() { return 'column-head'; }

  static get template() {
    return html`
      <style>
        :host {
          align-items: center;
          background-position: center;
          display: flex;
          justify-content: center;
          transition: background var(--transition-long, 1s);
        }
        :host(:not([disabled])) {
          cursor: pointer;
        }
        :host(:hover:not([disabled])) {
          background: white radial-gradient(circle, transparent 1%, white 1%)
          center/15000%;
        }
        :host(:active:not([disabled])) {
          background-color: var(--primary-color-medium, lightblue);
          background-size: 100%;
          transition: background 0s;
        }
        #icon {
          transition: color var(--transition-short, 0.5s);
        }
        #icon[empty] {
          color: transparent;
        }
      </style>

      <iron-icon
          id="icon"
          empty$="[[isIconEmpty_(disabled, name, sortColumn)]]"
          icon="[[getIcon_(sortDescending)]]">
      </iron-icon>
      <slot></slot>
    `;
  }

  isIconEmpty_(disabled, name, sortColumn) {
    return disabled || (name !== sortColumn);
  }

  getIcon_(sortDescending) {
    return sortDescending ? 'cp:arrow-downward' : 'cp:arrow-upward';
  }
}

ColumnHead.properties = {
  disabled: {
    type: Boolean,
    reflectToAttribute: true,
    value: false,
  },
  name: {
    type: String,
    value: '',
  },
  sortColumn: {
    type: String,
    value: '',
  },
  sortDescending: {
    type: Boolean,
    value: false,
  },
};

customElements.define(ColumnHead.is, ColumnHead);
