/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class TagFilter extends cp.ElementBase {
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
