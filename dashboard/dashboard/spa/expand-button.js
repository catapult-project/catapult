/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import ElementBase from './element-base.js';
import {TOGGLE} from './simple-redux.js';
import {html} from '/@polymer/polymer/polymer-element.js';

import {
  buildProperties,
  buildState,
} from './utils.js';

export default class ExpandButton extends ElementBase {
  static get is() { return 'expand-button'; }

  static get template() {
    return html`
      <style>
        :host {
          display: flex;
          cursor: pointer;
        }
        iron-icon {
          height: 20px;
          width: 20px;
        }
      </style>

      <iron-icon icon="[[getIcon_(isExpanded)]]">
      </iron-icon>
      <slot></slot>
    `;
  }

  ready() {
    super.ready();
    this.addEventListener('click', this.onClick_.bind(this));
  }

  async onClick_(event) {
    await this.dispatch('toggle', this.statePath);
  }

  getIcon_(isExpanded) {
    return ExpandButton.getIcon(isExpanded, this.horizontal, this.after);
  }
}

ExpandButton.getIcon = (isExpanded, horizontal, after) => {
  if (after) isExpanded = !isExpanded;
  if (horizontal) {
    return (isExpanded ? 'cp:left' : 'cp:right');
  }
  return (isExpanded ? 'cp:less' : 'cp:more');
};

const ExpandState = {
  isExpanded: options => options.isExpanded || false,
};

ExpandButton.properties = {
  ...buildProperties('state', ExpandState),
  horizontal: {
    type: Boolean,
    value: false,
  },
  after: {
    type: Boolean,
    value: false,
  },
};

ExpandButton.buildState = options => buildState(ExpandState, options);

ExpandButton.actions = {
  toggle: statePath => async(dispatch, getState) => {
    dispatch(TOGGLE(statePath + '.isExpanded'));
  },
};

ElementBase.register(ExpandButton);
