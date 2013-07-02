// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('ui');

base.exportTo('tracing.analysis', function() {
  var ObjectSnapshotView = ui.define('object-snapshot-view');

  ObjectSnapshotView.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.objectSnapshot_ = undefined;
    },

    set modelObject(obj) {
      this.objectSnapshot = obj;
    },

    get modelObject() {
      return this.objectSnapshot;
    },

    get objectSnapshot() {
      return this.objectSnapshot_;
    },

    set objectSnapshot(i) {
      this.objectSnapshot_ = i;
      this.updateContents();
    },

    updateContents: function() {
      throw new Error('Not implemented');
    }
  };

  ObjectSnapshotView.typeNameToViewInfoMap = {};
  ObjectSnapshotView.register = function(typeName,
                                         viewConstructor,
                                         opt_options) {
    if (ObjectSnapshotView.typeNameToViewInfoMap[typeName])
      throw new Error('Handler already registered for ' + typeName);
    var options = opt_options || {
      showInTrackView: true
    };
    ObjectSnapshotView.typeNameToViewInfoMap[typeName] = {
      constructor: viewConstructor,
      options: options
    };
  };

  ObjectSnapshotView.unregister = function(typeName) {
    if (ObjectSnapshotView.typeNameToViewInfoMap[typeName] === undefined)
      throw new Error(typeName + ' not registered');
    delete ObjectSnapshotView.typeNameToViewInfoMap[typeName];
  };

  ObjectSnapshotView.getViewInfo = function(typeName) {
    return ObjectSnapshotView.typeNameToViewInfoMap[typeName];
  };

  return {
    ObjectSnapshotView: ObjectSnapshotView
  };
});
