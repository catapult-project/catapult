/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class CpDialog extends Polymer.Element {
    static get is() { return 'cp-dialog'; }
  }
  customElements.define(CpDialog.is, CpDialog);
});
