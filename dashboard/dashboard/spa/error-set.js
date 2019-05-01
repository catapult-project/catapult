/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import '@polymer/polymer/lib/elements/dom-repeat.js';
import {PolymerElement, html} from '@polymer/polymer/polymer-element.js';

export default class ErrorSet extends PolymerElement {
  static get is() { return 'error-set'; }

  static get properties() {
    return {errors: Array};
  }

  static get template() {
    return html`
      <style>
        .error {
          color: var(--error-color, red);
        }
      </style>

      <dom-repeat items="[[errors]]" as="error">
        <template>
          <div class="error">
            [[error]]
          </div>
        </template>
      </dom-repeat>
    `;
  }
}
customElements.define(ErrorSet.is, ErrorSet);
