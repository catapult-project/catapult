// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the Settings class.
 */
base.defineModule('settings')
    .exportsTo('base', function() {

  /**
   * Settings is a simple wrapper around local storage, to make it easier
   * to test classes that have settings.
   *
   * @constructor
   */
  function Settings() {
    if ('G_testRunner' in global) {
      this.storage_ = {};
    } else {
      this.storage_ = localStorage;
    }
  }

  Settings.prototype = {
    get: function(key, opt_default) {
      key = this.namespace_(key);
      if (!(key in this.storage_))
        return opt_default;
      return String(this.storage_[key]);
    },

    set: function(key, value) {
      this.storage_[this.namespace_(key)] = String(value);
    },

    namespace_: function(key) {
      return "trace_viewer." + key;
    },
  };

  return {
    Settings: Settings
  }
});
