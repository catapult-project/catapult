// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireTemplate('cc.picture_debugger');
base.requireStylesheet('cc.picture_debugger');

base.require('cc.picture');
base.require('cc.picture_ops_list_view');
base.require('cc.picture_ops_chart_view');
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
      var node = base.instantiateTemplate('#picture-debugger-template');
      this.appendChild(node);

      this.pictureAsImageData_ = undefined;
      this.showOverdraw_ = false;

      this.sizeInfo_ = this.querySelector('.size');
      this.rasterArea_ = this.querySelector('raster-area');
      this.filename_ = this.querySelector('.filename');

      this.drawOpsChartView_ = new cc.PictureOpsChartView();

      var exportButton = this.querySelector('.export');
      exportButton.addEventListener(
          'click', this.onSaveAsSkPictureClicked_.bind(this));

      var overdrawCheckbox = ui.createCheckBox(
          this, 'showOverdraw',
          'pictureViewer.showOverdraw', false,
          'Show overdraw');

      var chartCheckbox = ui.createCheckBox(
          this, 'showChart',
          'pictureViewer.showChart', false,
          'Show timing chart');

      var pictureInfo = this.querySelector('picture-info');
      pictureInfo.appendChild(overdrawCheckbox);
      pictureInfo.appendChild(chartCheckbox);

      this.drawOpsView_ = new cc.PictureOpsListView();
      this.drawOpsView_.addEventListener(
          'selection-changed', this.onChangeDrawOps_.bind(this));

      var leftPanel = this.querySelector('left-panel');
      leftPanel.appendChild(this.drawOpsChartView_);
      leftPanel.appendChild(this.drawOpsView_);

      var middleDragHandle = new ui.DragHandle();
      middleDragHandle.horizontal = false;
      middleDragHandle.target = leftPanel;

      this.infoBar_ = new ui.InfoBar();
      this.rasterArea_.appendChild(this.infoBar_);

      this.insertBefore(middleDragHandle, this.rasterArea_);

      this.picture_ = undefined;

      // Add a mutation observer so that when the view is resized we can
      // update the chart view.
      this.mutationObserver_ = new MutationObserver(
          this.onMutation_.bind(this));
      this.mutationObserver_.observe(leftPanel, { attributes: true });
    },

    onMutation_: function(mutations) {

      for (var m = 0; m < mutations.length; m++) {
        // A style change would indicate that the element has resized
        // so we should re-render the chart.
        if (mutations[m].attributeName === 'style') {
          this.drawOpsChartView_.requiresRedraw = true;
          this.drawOpsChartView_.updateChartContents();
          break;
        }
      }
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
      this.drawOpsChartView_.picture = picture;
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
        this.infoBar_.addButton('More info...', function(e) {
          var overlay = new ui.Overlay();
          overlay.textContent = this.pictureAsImageData_.error;
          overlay.visible = true;
          e.stopPropagation();
          return false;
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
    },

    set showChart(chartShouldBeVisible) {
      if (chartShouldBeVisible)
        this.drawOpsChartView_.show();
      else
        this.drawOpsChartView_.hide();
    }
  };

  return {
    PictureDebugger: PictureDebugger
  };
});
