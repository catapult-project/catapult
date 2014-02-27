// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tvcm.ui');

tvcm.exportTo('telemetry.web_components', function() {
  /**
   * @constructor
   */
  var ResultsViewer = tvcm.ui.define('x-results-viewer');

  ResultsViewer.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.dataToView_ = undefined;
    },

    get dataToView() {
      return dataToView_;
    },

    set dataToView(dataToView) {
      this.dataToView_ = dataToView;
      this.updateContents_();
    },

    updateContents_: function() {
      this.textContent = JSON.stringify(this.dataToView_);
    }
  };

  return {
    ResultsViewer: ResultsViewer
  };
});
