// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.analysis.object_instance_view');
base.require('tracing.analysis.object_snapshot_view');
base.exportTo('tracing.analysis', function() {
  /*
   * Displays an object instance in a human readable form.
   * @constructor
   */
  var DefaultObjectSnapshotView = ui.define(
      tracing.analysis.ObjectSnapshotView);

  DefaultObjectSnapshotView.prototype = {
    __proto__: tracing.analysis.ObjectSnapshotView.prototype,

    decorate: function() {
    },

    updateContents: function() {
      var snapshot = this.objectSnapshot;
      if (!snapshot) {
        this.textContents = '';
        return;
      }
      var instance = snapshot.objectInstance;

      this.textContent =
        'Snapshot of ' + instance.typeName + '\n' +
        'TS: ' + snapshot.ts + '\n' +
        'ID: ' + snapshot.id + '\n';
    },
  };


  /**
   * Displays an object instance in a human readable form.
   * @constructor
   */
  var DefaultObjectInstanceView = ui.define(
      tracing.analysis.ObjectInstanceView);

  DefaultObjectInstanceView.prototype = {
    __proto__: tracing.analysis.ObjectInstanceView.prototype,

    decorate: function() {
    },

    updateContents: function() {
      var instance = this.objectInstance;
      if (!instance) {
        this.textContent = '';
        return;
      }

      this.textContent =
        'Type: ' + instance.typeName + '\n' +
        'ID: ' + instance.id + '\n';
    },
  };

  return {
    DefaultObjectSnapshotView: DefaultObjectSnapshotView,
    DefaultObjectInstanceView: DefaultObjectInstanceView
  };
});
