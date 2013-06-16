// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('cc.picture_debugger');

base.require('cc.picture');
base.require('tracing.analysis.generic_object_view');
base.require('ui.drag_handle');
base.require('ui.info_bar');
base.require('ui.list_view');
base.require('ui.overlay');

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
      this.controls_ = document.createElement('top-controls');
      this.infoBar_ = new ui.InfoBar();
      this.pictureDataView_ = new tracing.analysis.GenericObjectView();

      this.rasterResult_ = document.createElement('raster-result');
      this.rasterArea_ = document.createElement('raster-area');

      this.filename_ = document.createElement('input');
      this.filename_.classList.add('filename');
      this.filename_.type = 'text';
      this.filename_.value = 'skpicture.skp';
      this.controls_.appendChild(this.filename_);

      var saveButton = document.createElement('button');
      saveButton.textContent = 'Save SkPicture';
      saveButton.addEventListener(
          'click', this.onSaveAsSkPictureClicked_.bind(this));
      this.controls_.appendChild(saveButton);

      this.dragHandle_ = new ui.DragHandle();
      this.dragHandle_.horizontal = false;
      this.dragHandle_.target = this.pictureDataView_;

      this.appendChild(this.pictureDataView_);
      this.appendChild(this.dragHandle_);
      this.rasterArea_.appendChild(this.controls_);
      this.rasterArea_.appendChild(this.infoBar_);
      this.rasterArea_.appendChild(this.rasterResult_);
      this.appendChild(this.rasterArea_);

      this.picture_ = undefined;
    },

    onSaveAsSkPictureClicked_: function() {
      // Decode base64 data into a String
      var rawData = atob(this.picture_.getBase64SkpData());

      // Convert this String into an Uint8Array
      var length = rawData.length;
      var arrayBuffer = new ArrayBuffer(length);
      var uint8Array = new Uint8Array(arrayBuffer);
      for (var c = 0; c < length; c++)
        uint8Array[c] = rawData.charCodeAt(c);

      // Create a blob URL from the binary array.
      var blob = new Blob([uint8Array], {type: 'application/octet-binary'});
      var blobUrl = window.webkitURL.createObjectURL(blob);

      // Create a link and click on it. BEST API EVAR!
      var link = document.createElementNS('http://www.w3.org/1999/xhtml', 'a');
      link.href = blobUrl;
      link.download = this.filename_.value;
      var event = document.createEvent('MouseEvents');
      event.initMouseEvent(
          'click', true, false, window, 0, 0, 0, 0, 0,
          false, false, false, false, 0, null);
      link.dispatchEvent(event);
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
      this.infoBar_.visible = false;
      this.infoBar_.removeAllButtons();

      if (!this.picture_.image) {
        this.style.backgroundImage = '';
        if (!this.picture_.canRasterizeImage) {
          var details;
          if (!cc.PictureSnapshot.CanRasterize()) {
            details = cc.PictureSnapshot.HowToEnableRasterizing();
          } else {
            details = 'Your recording may be from an old Chrome version. ' +
                'The SkPicture format is not backward compatible.';
          }
          this.infoBar_.message = 'Cannot rasterize...';
          this.infoBar_.addButton('More info...', function() {
            var overlay = new ui.Overlay();
            overlay.textContent = details;
            overlay.visible = true;
            overlay.autoClose = true;
          });
          this.infoBar_.visible = true;
        } else {
          this.picture_.beginRasterizingImage(
              this.scheduleUpdateContents_.bind(this));
        }
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
