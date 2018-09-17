/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class ExpandButton extends cp.ElementBase {
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
    ...cp.buildProperties('state', ExpandState),
    horizontal: {
      type: Boolean,
      value: false,
    },
    after: {
      type: Boolean,
      value: false,
    },
  };

  ExpandButton.buildState = options => cp.buildState(ExpandState, options);

  ExpandButton.actions = {
    toggle: statePath => async(dispatch, getState) => {
      dispatch(Redux.TOGGLE(statePath + '.isExpanded'));
    },
  };

  cp.ElementBase.register(ExpandButton);

  return {
    ExpandButton,
  };
});
