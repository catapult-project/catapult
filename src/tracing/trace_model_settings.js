// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.settings');

base.exportTo('tracing', function() {
  var Settings = base.Settings;

  /**
   * A way to persist settings specific to parts of a trace model.
   *
   * This object should not be persisted because it builds up internal data
   * structures that map model objects to settings keys. It should thus be
   * created for the druation of whatever interaction(s) you're going to do with
   * model settings, and then discarded.
   *
   * This system works on a notion of an object key: for an object's key, it
   * considers all the other keys in the model. If it is unique, then the key is
   * persisted to base.Settings. However, if it is not unique, then the
   * setting is stored on the object itself. Thus, objects with unique keys will
   * be persisted across page reloads, whereas objects with nonunique keys will
   * not.
   */
  function TraceModelSettings(model) {
    this.model = model;
    this.objectsByKey_ = [];
    this.nonuniqueKeys_ = [];
    this.buildObjectsByKeyMap_();
    this.removeNonuniqueKeysFromSettings_();
  }

  TraceModelSettings.prototype = {
    buildObjectsByKeyMap_: function() {
      var objects = [this.model.kernel];
      objects.push.apply(objects,
                         base.dictionaryValues(this.model.processes));
      objects.push.apply(objects,
                         this.model.getAllThreads());
      var objectsByKey = {};
      var NONUNIQUE_KEY = 'nonuniqueKey';
      for (var i = 0; i < objects.length; i++) {
        var object = objects[i];
        var objectKey = object.getSettingsKey();
        if (!objectKey)
          continue;
        if (objectsByKey[objectKey] === undefined) {
          objectsByKey[objectKey] = object;
          continue;
        }
        objectsByKey[objectKey] = NONUNIQUE_KEY;
      }

      var nonuniqueKeys = {};
      base.dictionaryKeys(objectsByKey).forEach(function(objectKey) {
        if (objectsByKey[objectKey] !== NONUNIQUE_KEY)
          return;
        delete objectsByKey[objectKey];
        nonuniqueKeys[objectKey] = true;
      });

      this.nonuniqueKeys = nonuniqueKeys;
      this.objectsByKey_ = objectsByKey;
    },

    removeNonuniqueKeysFromSettings_: function() {
      var settings = Settings.get('trace_model_settings', {});
      var settingsChanged = false;
      base.dictionaryKeys(settings).forEach(function(objectKey) {
        if (!this.nonuniqueKeys[objectKey])
          return;
        settingsChanged = true;
        delete settings[objectKey];
      }, this);
      if (settingsChanged)
        Settings.set('trace_model_settings', settings);
    },

    hasUniqueSettingKey: function(object) {
      var objectKey = object.getSettingsKey();
      if (!objectKey)
        return false;
      return this.objectsByKey_[objectKey] !== undefined;
    },

    getSettingFor: function(object, objectLevelKey, defaultValue) {
      var objectKey = object.getSettingsKey();
      if (!objectKey || !this.objectsByKey_[objectKey]) {
        var ephemeralValue = object.ephemeralSettings[objectLevelKey];
        if (ephemeralValue !== undefined)
          return ephemeralValue;
        return defaultValue;
      }

      var settings = Settings.get('trace_model_settings', {});
      if (!settings[objectKey])
        settings[objectKey] = {};
      var value = settings[objectKey][objectLevelKey];
      if (value !== undefined)
        return value;
      return defaultValue;
    },

    setSettingFor: function(object, objectLevelKey, value) {
      var objectKey = object.getSettingsKey();
      if (!objectKey || !this.objectsByKey_[objectKey]) {
        object.ephemeralSettings[objectLevelKey] = value;
        return;
      }

      var settings = Settings.get('trace_model_settings', {});
      if (!settings[objectKey])
        settings[objectKey] = {};
      settings[objectKey][objectLevelKey] = value;
      Settings.set('trace_model_settings', settings);
    }
  };

  return {
    TraceModelSettings: TraceModelSettings
  };
});
