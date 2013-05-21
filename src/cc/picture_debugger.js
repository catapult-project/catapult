// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('cc.picture_debugger');

base.require('cc.picture');
base.require('tracing.analysis.generic_object_view');
base.require('ui.drag_handle');
base.require('ui.list_view');

base.exportTo('cc', function() {

  /**
   * PictureDebugger is a view of a PictureSnapshot for inspecting
   * the picture in detail. (e.g., timing information, etc.)
   *
   * @constructor
   */
  var PictureDebugger = ui.define('picture-debugger');

  PictureDebugger.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.pictureDataView_ = new tracing.analysis.GenericObjectView();
      this.rasterArea_ = document.createElement('raster-area');
      this.rasterArea_.classList.add('raster-area');

      this.dragHandle_ = new ui.DragHandle();
      this.dragHandle_.horizontal = false;
      this.dragHandle_.target = this.pictureDataView_;

      this.appendChild(this.pictureDataView_);
      this.appendChild(this.dragHandle_);
      this.appendChild(this.rasterArea_);

      this.picture_ = undefined;
    },

    get picture() {
      return this.picture_;
    },

    set picture(picture) {
      this.picture_ = picture;
      this.updateContents_();
    },

    scheduleUpdateContents_: function() {
      if (this.updateContentsPending_)
        return;
      this.updateContentsPending_ = true;
      webkitRequestAnimationFrame(this.updateContents_.bind(this));
    },

    updateContents_: function() {
      this.updateContentsPending_ = false;

      if (!this.picture_)
        return;

      if (!this.picture_.image) {
        this.style.backgroundImage = '';
        this.picture_.beginRenderingImage(
            this.scheduleUpdateContents_.bind(this));
      } else {
        this.rasterArea_.style.backgroundImage = 'url("' +
            this.picture_.image.src + '")';
      }

      this.pictureDataView_.object = this.picture_;
    }
  };

  return {
    PictureDebugger: PictureDebugger
  };
});
