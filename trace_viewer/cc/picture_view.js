// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.requireStylesheet('cc.picture_view');

tvcm.require('cc.picture');
tvcm.require('cc.picture_debugger');
tvcm.require('tracing.analysis.generic_object_view');
tvcm.require('tracing.analysis.object_snapshot_view');
tvcm.require('tracing.analysis.util');

tvcm.exportTo('cc', function() {

  /*
   * Displays a picture snapshot in a human readable form.
   * @constructor
   */
  var PictureSnapshotView = tvcm.ui.define(
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
  tracing.analysis.ObjectSnapshotView.register(
      'cc::LayeredPicture', PictureSnapshotView);

  return {
    PictureSnapshotView: PictureSnapshotView
  };

});
