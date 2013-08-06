// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('cc.picture_debugger');

base.require('cc.picture');
base.require('cc.picture_ops_list_view');
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
      this.pictureAsImageData_ = undefined;
      this.showOverdraw_ = false;

      this.leftPanel_ = document.createElement('left-panel');

      this.pictureInfo_ = document.createElement('picture-info');

      this.title_ = document.createElement('span');
      this.title_.textContent = 'Skia Picture';
      this.title_.classList.add('title');
      this.sizeInfo_ = document.createElement('span');
      this.sizeInfo_.classList.add('size');
      this.filename_ = document.createElement('input');
      this.filename_.classList.add('filename');
      this.filename_.type = 'text';
      this.filename_.value = 'skpicture.skp';
      var exportButton = document.createElement('button');
      exportButton.textContent = 'Export';
      exportButton.addEventListener(
          'click', this.onSaveAsSkPictureClicked_.bind(this));
      var overdrawCheckbox = ui.createCheckBox(
          this, 'showOverdraw',
          'pictureViewer.showOverdraw', false,
          'Show overdraw');
      this.pictureInfo_.appendChild(this.title_);
      this.pictureInfo_.appendChild(this.sizeInfo_);
      this.pictureInfo_.appendChild(document.createElement('br'));
      this.pictureInfo_.appendChild(this.filename_);
      this.pictureInfo_.appendChild(exportButton);
      this.pictureInfo_.appendChild(document.createElement('br'));
      this.pictureInfo_.appendChild(overdrawCheckbox);

      this.titleDragHandle_ = new ui.DragHandle();
      this.titleDragHandle_.horizontal = true;
      this.titleDragHandle_.target = this.pictureInfo_;

      this.drawOpsView_ = new cc.PictureOpsListView();
      this.drawOpsView_.addEventListener(
          'selection-changed', this.onChangeDrawOps_.bind(this));

      this.leftPanel_.appendChild(this.pictureInfo_);
      this.leftPanel_.appendChild(this.titleDragHandle_);
      this.leftPanel_.appendChild(this.drawOpsView_);

      this.middleDragHandle_ = new ui.DragHandle();
      this.middleDragHandle_.horizontal = false;
      this.middleDragHandle_.target = this.leftPanel_;

      this.infoBar_ = new ui.InfoBar();
      this.rasterArea_ = document.createElement('raster-area');

      this.appendChild(this.leftPanel_);
      this.appendChild(this.middleDragHandle_);
      this.rasterArea_.appendChild(this.infoBar_);
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
      this.drawOpsView_.picture = picture;
      this.picture_ = picture;
      this.rasterize_();

      this.scheduleUpdateContents_();
    },

    scheduleUpdateContents_: function() {
      if (this.updateContentsPending_)
        return;
      this.updateContentsPending_ = true;
      base.requestAnimationFrameInThisFrameIfPossible(
          this.updateContents_.bind(this)
      );
    },

    updateContents_: function() {
      this.updateContentsPending_ = false;

      if (this.picture_) {
        this.sizeInfo_.textContent = '(' +
            this.picture_.layerRect.width + ' x ' +
            this.picture_.layerRect.height + ')';
      }

      // Return if picture hasn't finished rasterizing.
      if (!this.pictureAsImageData_)
        return;

      this.infoBar_.visible = false;
      this.infoBar_.removeAllButtons();
      if (this.pictureAsImageData_.error) {
        this.infoBar_.message = 'Cannot rasterize...';
        this.infoBar_.addButton('More info...', function() {
          var overlay = new ui.Overlay();
          overlay.textContent = this.pictureAsImageData_.error;
          overlay.visible = true;
          overlay.obeyCloseEvents = true;
        }.bind(this));
        this.infoBar_.visible = true;
      }

      // FIXME(pdr): Append the canvas instead of using a background image.
      if (this.pictureAsImageData_.imageData) {
        var canvas = this.pictureAsImageData_.asCanvas();
        var imageUrl = canvas.toDataURL();
        canvas.width = 0; // Free the GPU texture.
        this.rasterArea_.style.backgroundImage = 'url("' + imageUrl + '")';
      } else {
        this.rasterArea_.style.backgroundImage = '';
      }
    },

    rasterize_: function() {
      if (this.picture_) {
        this.picture_.rasterize(
            {
              stopIndex: this.drawOpsView_.selectedOpIndex,
              showOverdraw: this.showOverdraw_
            },
            this.onRasterComplete_.bind(this));
      }
    },

    onRasterComplete_: function(pictureAsImageData) {
      this.pictureAsImageData_ = pictureAsImageData;
      this.scheduleUpdateContents_();
    },

    onChangeDrawOps_: function() {
      this.rasterize_();
      this.scheduleUpdateContents_();
    },

    set showOverdraw(v) {
      this.showOverdraw_ = v;
      this.rasterize_();
    }
  };

  return {
    PictureDebugger: PictureDebugger
  };
});
