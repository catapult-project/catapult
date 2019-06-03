/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {LitElement, html, css} from 'lit-element';

export default class ErrorSet extends LitElement {
  static get properties() {
    return {errors: Array};
  }

  static get styles() {
    return css`
      .error {
        color: var(--error-color, red);
      }
    `;
  }

  render() {
    return html`${(this.errors || []).map(error =>
      html`<div class="error">${error}</div>`)}`;
  }
}
customElements.define('error-set', ErrorSet);
