/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './cp-icon.js';
import {ElementBase, STORE} from './element-base.js';
import {TOGGLE} from './simple-redux.js';
import {get} from 'dot-prop-immutable';
import {html, css} from 'lit-element';

export class ExpandButton extends ElementBase {
  static get is() { return 'expand-button'; }

  static get properties() {
    return {
      horizontal: {type: Boolean, value: false},
      after: {type: Boolean, value: false},

      statePath: String,
      isExpanded: Boolean,
    };
  }

  static buildState(options = {}) {
    return {
      isExpanded: options.isExpanded || false,
    };
  }

  static get styles() {
    return css`
      :host {
        display: flex;
        cursor: pointer;
      }
    `;
  }

  render() {
    const icon = ExpandButton.getIcon(
        this.isExpanded, this.horizontal, this.after);
    return html`
      <cp-icon .icon="${icon}"></cp-icon>
      <slot></slot>
    `;
  }

  constructor() {
    super();
    this.addEventListener('click', this.onClick_.bind(this));
  }

  async onClick_(event) {
    STORE.dispatch(TOGGLE(this.statePath + '.isExpanded'));
  }

  static getIcon(isExpanded, horizontal, after) {
    if (after) isExpanded = !isExpanded;
    if (horizontal) {
      return (isExpanded ? 'left' : 'right');
    }
    return (isExpanded ? 'less' : 'more');
  }
}

ElementBase.register(ExpandButton);
