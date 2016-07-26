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
  SdchView.BLACKLIST_TBODY_ID = 'sdch-view-blacklist-tbody';
  SdchView.NUM_DICTIONARIES_LOADED_ID = 'sdch-view-num-dictionaries-loaded';
  SdchView.DICTIONARIES_TBODY_ID = 'sdch-view-dictionaries-tbody';

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

      $(SdchView.SDCH_ENABLED_SPAN_ID).textContent =
          !!sdchInfo.sdch_enabled;

      $(SdchView.NUM_DICTIONARIES_LOADED_ID).textContent =
          sdchInfo.dictionaries.length;

      var tbodyDictionaries = $(SdchView.DICTIONARIES_TBODY_ID);
      tbodyDictionaries.innerHTML = '';

      // Fill in the dictionaries table.
      for (var i = 0; i < sdchInfo.dictionaries.length; ++i) {
        var d = sdchInfo.dictionaries[i];
        var tr = addNode(tbodyDictionaries, 'tr');

        addNodeWithText(tr, 'td', d.domain);
        addNodeWithText(tr, 'td', d.path);
        addNodeWithText(tr, 'td',
            d.ports ? d.ports.join(', ') : '');
        addNodeWithText(tr, 'td', d.server_hash);
        addNodeWithText(tr, 'td', d.client_hash);
        addNodeWithText(tr, 'td', d.url);
      }

      var tbodyBlacklist = $(SdchView.BLACKLIST_TBODY_ID);
      tbodyBlacklist.innerHTML = '';

      // Fill in the blacklisted table.
      for (var i = 0; i < sdchInfo.blacklisted.length; ++i) {
        var b = sdchInfo.blacklisted[i];
        var tr = addNode(tbodyBlacklist, 'tr');

        addNodeWithText(tr, 'td', d.domain);
        addNodeWithText(tr, 'td', d.sdchProblemCodeToString(reason));
        addNodeWithText(tr, 'td', d.tries);
      }

      return true;
    },
  };

  return SdchView;
})();

