/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class PlaceHolder extends Polymer.Element {
    static get is() { return 'place-holder'; }

    static get template() {
      return Polymer.html`
        <style>
          :host {
            position: relative;
            display: flex;
          }

          #container {
            position: absolute;
            display: flex;
            align-items: center;
            justify-content: center;
          }

          #content {
            background: var(--background-color, white);
            padding: 8px;
          }

          :host, #container, svg {
            width: 100%;
            height: 100%;
          }

          pattern rect {
            fill: var(--neutral-color-light, lightgrey);
          }
        </style>

        <div id="container">
          <div id="content">
            <slot></slot>
          </div>
        </div>

        <svg>
          <pattern id="pattern"
                  x="0" y="0" width="20" height="20"
                  patternUnits="userSpaceOnUse">
            <rect x="0" width="10" height="10" y="0" />
            <rect x="10" width="10" height="10" y="10" />
          </pattern>

          <rect fill="url(#pattern)" x="0" y="0" width="100%" height="100%" />
        </svg>
      `;
    }
  }

  customElements.define(PlaceHolder.is, PlaceHolder);
  return {PlaceHolder};
});
