/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import OptionGroup from './option-group.js';
import {ElementBase, STORE} from './element-base.js';
import {get} from './utils.js';
import {html, css} from 'lit-element';

export default class TagFilter extends ElementBase {
  static get is() { return 'tag-filter'; }

  static get properties() {
    return {
      statePath: String,
      tags: Object,
    };
  }

  static buildState(options) {
    const tags = OptionGroup.buildState(options);
    tags.map = options.map || new Map();
    return {tags};
  }

  static get styles() {
    return css`
      #container {
        align-items: center;
        border-right: 1px solid black;
        display: flex;
        flex-direction: column;
        height: 100%;
        padding-right: 8px;
      }
      #head {
        padding: 4px;
        color: var(--neutral-color-dark, grey);
        font-weight: bold;
      }
    `;
  }

  render() {
    if (!this.tags || !this.tags.options || (this.tags.options.length === 0)) {
      return html``;
    }
    return html`
      <div id="container">
        <span id="tag_head">Tags</span>
        <option-group
            .statePath="${this.statePath}.tags"
            .rootStatePath="${this.statePath}.tags"
            @option-select="${this.onTagSelect_}">
        </option-group>
      </div>
    `;
  }

  onTagSelect_(event) {
    STORE.dispatch({
      type: TagFilter.reducers.filter.name,
      statePath: this.statePath,
    });
  }
}

TagFilter.reducers = {
  filter: state => {
    let testCases = new Set();
    let selectedOptions = [];
    if (state.tags && state.tags.selectedOptions &&
        state.tags.selectedOptions.length) {
      for (const tag of state.tags.selectedOptions) {
        const tagCases = state.tags.map.get(tag);
        if (!tagCases) continue;
        for (const testCase of tagCases) {
          testCases.add(testCase);
        }
      }
      testCases = [...testCases].sort();
      selectedOptions = [...testCases];
    } else {
      testCases = [...state.optionValues].sort();
      selectedOptions = [];
    }
    const options = [];
    if (testCases.length) {
      options.push({
        label: `All test cases`,
        isExpanded: true,
        options: OptionGroup.groupValues(testCases),
      });
    }
    return {...state, options, selectedOptions};
  },
};

ElementBase.register(TagFilter);
