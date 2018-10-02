/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
(() => {
  class CpToast extends Polymer.Element {
    static get is() { return 'cp-toast'; }

    /*
     * Autocloses after `wait` ms if open() is not called again in the interim.
     * Does not autoclose if `wait` is false.
     * `wait` can also be a Promise.
     */
    async open(wait = 10000) {
      this.opened = true;
      if (!wait) return;
      const start = this.openId_ = tr.b.GUID.allocateSimple();
      if (typeof wait === 'number') wait = cp.timeout(wait);
      await wait;
      if (this.openId_ !== start) return;
      this.opened = false;
    }
  }

  CpToast.properties = {
    opened: {
      type: Boolean,
      value: false,
      reflectToAttribute: true,
    },
  };

  customElements.define(CpToast.is, CpToast);
})();
