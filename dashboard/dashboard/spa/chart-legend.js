/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class ChartLegend extends Polymer.Element {
    static get is() { return 'chart-legend'; }

    async onLeafMouseOver_(event) {
      this.dispatchEvent(new CustomEvent('leaf-mouseover', {
        bubbles: true,
        composed: true,
        detail: event.model.item,
      }));
    }

    async onLeafMouseOut_(event) {
      this.dispatchEvent(new CustomEvent('leaf-mouseout', {
        bubbles: true,
        composed: true,
        detail: event.model.item,
      }));
    }

    async onLeafClick_(event) {
      event.stopPropagation();
      this.dispatchEvent(new CustomEvent('leaf-click', {
        bubbles: true,
        composed: true,
        detail: event.model.item,
      }));
    }
  }

  ChartLegend.properties = {
    items: {type: Array},
  };

  customElements.define(ChartLegend.is, ChartLegend);

  return {
    ChartLegend,
  };
});
