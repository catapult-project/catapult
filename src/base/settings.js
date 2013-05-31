// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the Settings object.
 */
base.exportTo('base', function() {
  var storage_ = localStorage;

  /**
   * Settings is a simple wrapper around local storage, to make it easier
   * to test classes that have settings.
   *
   * May be called as new base.Settings() or simply base.Settings()
   * @constructor
   */
  function Settings() {
    return Settings;
  };

  /**
   * Get the setting with the given name.
   *
   * @param {string} key The name of the setting.
   * @param {string=} opt_default The default value to return if not set.
   * @param {string=} opt_namespace If set, the setting name will be prefixed
   * with this namespace, e.g. "categories.settingName". This is useful for
   * a set of related settings.
   */
  Settings.get = function(key, opt_default, opt_namespace) {
    key = Settings.namespace_(key, opt_namespace);
    var rawVal = storage_.getItem(key);
    if (rawVal === null || rawVal === undefined)
      return opt_default;

    // Old settings versions used to stringify objects instead of putting them
    // into JSON. If those are encountered, parse will fail. In that case,
    // "upgrade" the setting to the default value.
    try {
      return JSON.parse(rawVal).value;
    } catch (e) {
      storage_.removeItem(Settings.namespace_(key, opt_namespace));
      return opt_default;
    }
  },

  /**
   * Set the setting with the given name to the given value.
   *
   * @param {string} key The name of the setting.
   * @param {string} value The value of the setting.
   * @param {string=} opt_namespace If set, the setting name will be prefixed
   * with this namespace, e.g. "categories.settingName". This is useful for
   * a set of related settings.
   */
  Settings.set = function(key, value, opt_namespace) {
    if (value === undefined)
      throw new Error('Settings.set: value must not be undefined');
    var v = JSON.stringify({value: value});
    storage_.setItem(Settings.namespace_(key, opt_namespace), v);
  },

  /**
   * Return a list of all the keys, or all the keys in the given namespace
   * if one is provided.
   *
   * @param {string=} opt_namespace If set, only return settings which
   * begin with this prefix.
   */
  Settings.keys = function(opt_namespace) {
    var result = [];
    opt_namespace = opt_namespace || '';
    for (var i = 0; i < storage_.length; i++) {
      var key = storage_.key(i);
      if (Settings.isnamespaced_(key, opt_namespace))
        result.push(Settings.unnamespace_(key, opt_namespace));
    }
    return result;
  },

  Settings.isnamespaced_ = function(key, opt_namespace) {
    return key.indexOf(Settings.normalize_(opt_namespace)) == 0;
  },

  Settings.namespace_ = function(key, opt_namespace) {
    return Settings.normalize_(opt_namespace) + key;
  },

  Settings.unnamespace_ = function(key, opt_namespace) {
    return key.replace(Settings.normalize_(opt_namespace), '');
  },

  /**
   * All settings are prefixed with a global namespace to avoid collisions.
   * Settings may also be namespaced with an additional prefix passed into
   * the get, set, and keys methods in order to group related settings.
   * This method makes sure the two namespaces are always set properly.
   */
  Settings.normalize_ = function(opt_namespace) {
    return Settings.NAMESPACE + (opt_namespace ? opt_namespace + '.' : '');
  }

  Settings.setAlternativeStorageInstance = function(instance) {
    storage_ = instance;
  }
  Settings.getAlternativeStorageInstance = function() {
    if (storage_ === localStorage)
      return undefined;
    return storage_;
  }

  Settings.NAMESPACE = 'trace-viewer';

  return {
    Settings: Settings
  };
});
