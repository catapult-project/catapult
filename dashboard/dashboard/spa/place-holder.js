/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class PlaceHolder extends Polymer.Element {
    static get is() { return 'place-holder'; }
  }

  customElements.define(PlaceHolder.is, PlaceHolder);
  return {PlaceHolder};
});
