// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * This view displays information related to SDCH.
 *
 * Shows loaded dictionaries, blacklisted domains and SDCH errors.
 */
var SdchView = (function() {
  'use strict';

  // We inherit from DivView.
  var superClass = DivView;

  /**
   * @constructor
   */
  function SdchView() {
    assertFirstConstructorCall(SdchView);

    // Call superclass's constructor.
    superClass.call(this, SdchView.MAIN_BOX_ID);

    // Register to receive changes to the SDCH info.
    g_browser.addSdchInfoObserver(this, false);
  }

  SdchView.TAB_ID = 'tab-handle-sdch';
  SdchView.TAB_NAME = 'SDCH';
  SdchView.TAB_HASH = '#sdch';

  // IDs for special HTML elements in sdch_view.html
  SdchView.MAIN_BOX_ID = 'sdch-view-tab-content';
  SdchView.SDCH_ENABLED_SPAN_ID = 'sdch-view-sdch-enabled';
  SdchView.SECURE_SCHEME_SUPPORT_SPAN_ID = 'sdch-view-secure-scheme-support';
  SdchView.BLACKLIST_TBODY_ID = 'sdch-view-blacklist-body';
  SdchView.DICTIONARIES_TBODY_ID = 'sdch-view-dictionaries-body';

  cr.addSingletonGetter(SdchView);

  SdchView.prototype = {
    // Inherit the superclass's methods.
    __proto__: superClass.prototype,

    onLoadLogFinish: function(data) {
      return this.onSdchInfoChanged(data.sdchInfo);
    },

    onSdchInfoChanged: function(sdchInfo) {
      if (!sdchInfo || typeof(sdchInfo.sdch_enabled) === 'undefined')
        return false;
      // TODO(rayraymond): Update DOM without use of jstemplate.
      // var input = new JsEvalContext(sdchInfo);
      // jstProcess(input, $(SdchView.MAIN_BOX_ID));
      return true;
    },
  };

  return SdchView;
})();

