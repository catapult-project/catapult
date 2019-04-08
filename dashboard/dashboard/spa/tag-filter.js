/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class TagFilter extends cp.ElementBase {
    static get template() {
      return Polymer.html`
        <style>
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
        </style>

        <template is="dom-if" if="[[!isEmpty_(tags.options)]]">
          <div id="container">
            <span id="tag_head">Tags</span>
            <option-group
                state-path="[[statePath]].tags"
                root-state-path="[[statePath]].tags"
                on-option-select="onTagSelect_">
            </option-group>
          </div>
        </template>
      `;
    }

    onTagSelect_(event) {
      this.dispatch('filter', this.statePath);
    }
  }

  TagFilter.State = {
    tags: options => {
      const tags = cp.OptionGroup.buildState(options);
      tags.map = options.map || new Map();
      return tags;
    },
  };

  TagFilter.properties = cp.buildProperties('state', TagFilter.State);
  TagFilter.buildState = options => cp.buildState(
      TagFilter.State, options);

  TagFilter.actions = {
    filter: statePath => async(dispatch, getState) => {
      dispatch({
        type: TagFilter.reducers.filter.name,
        statePath,
      });
    },
  };

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
          options: cp.OptionGroup.groupValues(testCases),
        });
      }
      return {...state, options, selectedOptions};
    },
  };

  cp.ElementBase.register(TagFilter);

  return {TagFilter};
});
