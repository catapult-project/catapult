// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('cc.picture_view');

base.require('cc.picture');
base.require('cc.picture_debugger');
base.require('tracing.analysis.generic_object_view');
base.require('tracing.analysis.object_snapshot_view');
base.require('tracing.analysis.util');

base.exportTo('cc', function() {

  /*
   * Displays a picture snapshot in a human readable form.
   * @constructor
   */
  var PictureSnapshotView = ui.define(
      'picture-snapshot-view',
      tracing.analysis.ObjectSnapshotView);

  PictureSnapshotView.prototype = {
    __proto__: tracing.analysis.ObjectSnapshotView.prototype,

    decorate: function() {
      this.classList.add('picture-snapshot-view');
      this.pictureDebugger_ = new cc.PictureDebugger();
      this.appendChild(this.pictureDebugger_);
    },

    updateContents: function() {
      if (this.objectSnapshot_ && this.pictureDebugger_)
        this.pictureDebugger_.picture = this.objectSnapshot_;
    }
  };

  tracing.analysis.ObjectSnapshotView.register(
      'cc::Picture', PictureSnapshotView);

  return {
    PictureSnapshotView: PictureSnapshotView
  };

});
