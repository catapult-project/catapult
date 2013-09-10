// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('gpu.state_view');

base.require('tracing.analysis.object_snapshot_view');
base.require('tracing.analysis.util');

base.exportTo('gpu', function() {

  /*
   * Displays a GPU state snapshot in a human readable form.
   * @constructor
   */
  var StateSnapshotView = ui.define(
      'gpu-state-snapshot-view',
      tracing.analysis.ObjectSnapshotView);

  StateSnapshotView.prototype = {
    __proto__: tracing.analysis.ObjectSnapshotView.prototype,

    decorate: function() {
      this.classList.add('gpu-state-snapshot-view');
      this.screenshotImage_ = document.createElement('img');
      this.appendChild(this.screenshotImage_);
    },

    updateContents: function() {
      if (this.objectSnapshot_ && this.objectSnapshot_.screenshot) {
        this.screenshotImage_.src = 'data:image/png;base64,' +
            this.objectSnapshot_.screenshot;
      }
    }
  };

  tracing.analysis.ObjectSnapshotView.register(
      'gpu::State', StateSnapshotView);

  return {
    StateSnapshotView: StateSnapshotView
  };

});
