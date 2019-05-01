/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {PolymerElement, html} from '@polymer/polymer/polymer-element.js';

export default class CpDialog extends PolymerElement {
  static get is() { return 'cp-dialog'; }

  static get template() {
    return html`
      <style>
        :host {
          background: rgba(0, 0, 0, 0.8);
          display: flex;
          height: 100%;
          justify-content: center;
          align-items: center;
          left: 0;
          position: fixed;
          top: 0;
          width: 100%;
          z-index: var(--layer-drawer, 200);
        }
      </style>
      <slot></slot>
    `;
  }
}
customElements.define(CpDialog.is, CpDialog);
