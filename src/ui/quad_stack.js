// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('ui.quad_stack');

base.require('base.bbox2');
base.require('base.quad');
base.require('base.raf');
base.require('ui.quad_view');
base.require('cc.region');

base.exportTo('ui', function() {
  var QuadView = ui.QuadView;

  function lerp(a, b, interp) {
    return (a * (1 - interp)) +
        (b * interp);
  }

  function validateQuads(quads) {
    for (var i = 0; i < quads.length; i++) {
      if (quads[i].stackingGroupId === undefined)
        throw new Error('All quads must have stackingGroupIds');
    }
  }

  /**
   * @constructor
   */
  var QuadStack = ui.define('quad-stack');

  QuadStack.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.contentContainer_ = document.createElement('view-container');
      this.appendChild(this.contentContainer_);
      this.viewport_ = undefined;
      this.quads_ = undefined;
      this.deviceViewportSizeForFrame_ = undefined;

      this.onMouseDown_ = this.onMouseDown_.bind(this);
      this.onMouseMove_ = this.onMouseMove_.bind(this);
      this.onMouseUp_ = this.onMouseUp_.bind(this);
      this.addEventListener('mousedown', this.onMouseDown_);

      this.cameraStart_ = {x: 0, y: 0};
      this.rotations_ = {x: 0, y: 0};
      this.rotationStart_ = {x: 0, y: 0};
      this.matrixParameters_ = {
        thicknessRatio: 0.012, // Ratio of thickness to world size.
        strengthRatioX: 0.7, // Ratio of mousemove X pixels to degrees rotated.
        strengthRatioY: 0.25 // Ratio of mousemove Y pixels to degrees rotated.
      };
    },

    setQuadsViewportAndDeviceViewportSize: function(
        quads, viewport, deviceViewportSizeForFrame, opt_insideRAF) {
      validateQuads(quads);
      this.quads_ = quads;
      this.viewport_ = viewport;
      this.deviceViewportSizeForFrame_ = deviceViewportSizeForFrame;
      this.updateContents_();
      if (opt_insideRAF && this.repaintPending_)
        this.repaint_();
    },

    get quads() {
      return this.quads_;
    },

    set quads(quads) {
      validateQuads(quads);
      this.quads_ = quads;
      this.updateContents_();
    },

    get viewport() {
      return this.viewport_;
    },

    set viewport(viewport) {
      this.viewport_ = viewport;
      this.updateContents_();
    },

    get deviceViewportSizeForFrame() {
      return this.deviceViewportSizeForFrame_;
    },

    set deviceViewportSizeForFrame(deviceViewportSizeForFrame) {
      this.deviceViewportSizeForFrame_ = deviceViewportSizeForFrame;
      this.updateContents_();
    },

    updateContents_: function() {
      var percX, percY;
      // TODO(nduca): This exists to get the stack to appear centered around the
      // center of the stack. But, the way this was done makes the quad stack
      // un-shrinkable. We need a better way.
      if (false) {
        if (this.viewport_) {
          var layoutRect = this.viewport_.layoutRect;
          percX = 100 * (Math.abs(layoutRect.x) / layoutRect.width);
          percX = 100 * (Math.abs(layoutRect.y) / layoutRect.height);
          this.style.width = layoutRect.width + 'px';
          this.style.height = layoutRect.height + 'px';
        } else {
          percX = '50';
          percY = '50';
        }
        this.style.webkitPerspectiveOrigin = percX + '% ' + percY + '%';
      }

      // Build the stacks.
      var stackingGroupsById = {};
      var quads = this.quads;
      for (var i = 0; i < quads.length; i++) {
        var quad = quads[i];
        if (stackingGroupsById[quad.stackingGroupId] === undefined)
          stackingGroupsById[quad.stackingGroupId] = [];
        stackingGroupsById[quad.stackingGroupId].push(quad);
      }

      // Get rid of old quad views if needed.
      var numStackingGroups = base.dictionaryValues(stackingGroupsById).length;
      while (this.contentContainer_.children.length > numStackingGroups) {
        var n = this.contentContainer_.children.length - 1;
        this.contentContainer_.removeChild(
            this.contentContainer_.children[n]);
      }

      // Helper function to create a new quad view and track the current one.
      var that = this;
      var curQuadViewIndex = -1;
      var curQuadView = undefined;
      function appendNewQuadView() {
        curQuadViewIndex++;
        if (curQuadViewIndex < that.contentContainer_.children.length) {
          curQuadView = that.contentContainer_.children[curQuadViewIndex];
        } else {
          curQuadView = new QuadView();
          that.contentContainer_.appendChild(curQuadView);
        }
        curQuadView.quads = undefined;
        curQuadView.viewport = that.viewport_;
        curQuadView.pendingQuads = [];
        curQuadView.region = new cc.Region();
        return curQuadView;
      }


      appendNewQuadView();
      for (var stackingGroupId in stackingGroupsById) {
        var stackingGroup = stackingGroupsById[stackingGroupId];
        var bbox = new base.BBox2();
        stackingGroup.forEach(function(q) { bbox.addQuad(q); });
        var bboxRect = bbox.asRect();

        if (curQuadView.region.rectIntersects(bboxRect))
          appendNewQuadView();
        curQuadView.region.rects.push(bboxRect);
        stackingGroup.forEach(function(q) {
          curQuadView.pendingQuads.push(q);
        });
      }

      for (var i = 0; i < this.contentContainer_.children.length; i++) {
        var child = this.contentContainer_.children[i];
        if (i != this.contentContainer_.children.length - 1) {
          child.deviceViewportSizeForFrame = undefined;
        } else {
          child.drawDeviceViewportMask = true;
          child.deviceViewportSizeForFrame =
              this.deviceViewportSizeForFrame_;
        }
        child.quads = child.pendingQuads;
        delete child.pendingQuads;
      }

      this.scheduleRepaint_();
    },

    scheduleRepaint_: function() {
      if (this.repaintPending_)
        return;
      this.repaintPending_ = true;
      base.requestAnimationFrameInThisFrameIfPossible(
          this.repaint_, this);
    },

    repaint_: function() {
      if (!this.repaintPending_)
        return;
      this.repaintPending_ = false;
      var layers = this.contentContainer_.children;
      var numLayers = layers.length;

      var vpThickness;
      if (this.viewport_) {
        vpThickness = this.matrixParameters_.thicknessRatio *
            Math.min(this.viewport_.worldRect.width,
                     this.viewport_.worldRect.height);
      } else {
        vpThickness = 0;
      }
      vpThickness = Math.max(vpThickness, 15);

      // When viewing the stack head-on, we want no foreshortening effects. As
      // we move off axis, let the thickness grow as well as the amount of
      // perspective foreshortening.
      var maxRotation = Math.max(Math.abs(this.rotations_.x),
                                 Math.abs(this.rotations_.y));
      var clampLimit = 30;
      var clampedMaxRotation = Math.min(maxRotation, clampLimit);
      var percentToClampLimit = clampedMaxRotation / clampLimit;
      var persp = Math.pow(Math.E,
                           lerp(Math.log(5000), Math.log(500),
                                percentToClampLimit));
      this.style.webkitPerspective = persp;
      var effectiveThickness = vpThickness * percentToClampLimit;

      // Set depth of each layer such that they center around 0.
      var deepestLayerZ = -effectiveThickness * 0.5;
      var depthIncreasePerLayer = effectiveThickness /
          Math.max(1, numLayers - 1);
      for (var i = 0; i < numLayers; i++) {
        var layer = layers[i];
        var newDepth = deepestLayerZ + i * depthIncreasePerLayer;
        layer.style.webkitTransform = 'translateZ(' + newDepth + 'px)';
      }

      // Set rotation matrix to whatever is stored.
      var transformString = '';
      transformString += 'rotateX(' + this.rotations_.x + 'deg)';
      transformString += ' rotateY(' + this.rotations_.y + 'deg)';
      this.contentContainer_.style.webkitTransform = transformString;
    },

    updateCameraStart_: function(x, y) {
      this.cameraStart_.x = x;
      this.cameraStart_.y = y;
      this.rotationStart_.x = this.rotations_.x;
      this.rotationStart_.y = this.rotations_.y;
    },

    updateCamera_: function(x, y) {
      var delta = {
        x: this.cameraStart_.x - x,
        y: this.cameraStart_.y - y
      };
      // update new rotation matrix (note the parameter swap)
      // "strength" is ration between mouse dist and rotation amount.
      this.rotations_.x = this.rotationStart_.x + delta.y *
          this.matrixParameters_.strengthRatioY;
      this.rotations_.y = this.rotationStart_.y + -delta.x *
          this.matrixParameters_.strengthRatioX;
      this.scheduleRepaint_();
    },

    onMouseDown_: function(e) {
      this.updateCameraStart_(e.x, e.y);
      document.addEventListener('mousemove', this.onMouseMove_);
      document.addEventListener('mouseup', this.onMouseUp_);
      e.preventDefault();
      return true;
    },

    onMouseMove_: function(e) {
      this.updateCamera_(e.x, e.y);
    },

    onMouseUp_: function(e) {
      document.removeEventListener('mousemove', this.onMouseMove_);
      document.removeEventListener('mouseup', this.onMouseUp_);
      this.updateCamera_(e.x, e.y);
    }

  };


  return {
    QuadStack: QuadStack
  };
});
