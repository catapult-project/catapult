// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('ui');

base.exportTo('tracing.analysis', function() {
  var ObjectSnapshotView = ui.define('div');

  ObjectSnapshotView.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.objectSnapshot_ = undefined;
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

  ObjectSnapshotView.typeNameToViewConstructorMap = {};
  ObjectSnapshotView.register = function(typeName, viewConstructor) {
    if (ObjectSnapshotView.typeNameToViewConstructorMap[typeName])
      throw new Error('Handler already registerd for ' + typeName);
    ObjectSnapshotView.typeNameToViewConstructorMap[typeName] =
      viewConstructor;
  };

  ObjectSnapshotView.getViewConstructor = function(typeName) {
    return ObjectSnapshotView.typeNameToViewConstructorMap[typeName];
  };

  return {
    ObjectSnapshotView: ObjectSnapshotView,
  };
});
