/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class ColumnHead extends Polymer.Element {
    static get is() { return 'column-head'; }

    isIconEmpty_(disabled, name, sortColumn) {
      return disabled || (name !== sortColumn);
    }

    getIcon_(sortDescending) {
      return sortDescending ? 'cp:arrow-downward' : 'cp:arrow-upward';
    }
  }

  ColumnHead.properties = {
    disabled: {
      type: Boolean,
      reflectToAttribute: true,
      value: false,
    },
    name: {
      type: String,
      value: '',
    },
    sortColumn: {
      type: String,
      value: '',
    },
    sortDescending: {
      type: Boolean,
      value: false,
    },
  };

  customElements.define(ColumnHead.is, ColumnHead);

  return {ColumnHead};
});
