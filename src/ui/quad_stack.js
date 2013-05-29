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

      this.rAF_ = null;
      this.depth_ = 70;
      this.cameraStart_ = {x: null, y: null};
      this.rotations_ = {x: null, y: null};
      this.rotationStart_ = {x: null, y: null};
      this.matrixParameters_ = {
          strengthRatio: 0.7, // ratio of mousemove pixels to degrees rotated.
          depthRatio: 1.0     // ratio of depth to depth pixels.
      };
    },

    get quads() {
      return this.quads_;
    },

    set quads(quads) {
      for (var i = 0; i < quads.length; i++) {
        if (quads[i].stackingGroupId === undefined)
          throw new Error('All quads must have stackingGroupIds');
      }
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
      this.contentContainer_.textContent = '';

      var that = this;
      function appendNewQuadView() {
        var quadView = new QuadView();
        quadView.viewport = that.viewport_;
        quadView.deviceViewportSizeForFrame = that.deviceViewportSizeForFrame_;
        quadView.pendingQuads = [];
        quadView.region = new cc.Region();
        that.contentContainer_.appendChild(quadView);
        return quadView;
      }

      // TODO(pdr): Remove me once the Quad Stack stabalizes.
      // Set this conditional to true to disable the 3d view.
      if (false) {
        var qv = appendNewQuadView();
        qv.quads = this.quads_;
        return;
      }

      var stackingGroupsById = {};
      var quads = this.quads;
      for (var i = 0; i < quads.length; i++) {
        var quad = quads[i];
        if (stackingGroupsById[quad.stackingGroupId] === undefined)
          stackingGroupsById[quad.stackingGroupId] = [];
        stackingGroupsById[quad.stackingGroupId].push(quad);
      }

      appendNewQuadView();
      for (var stackingGroupId in stackingGroupsById) {
        var stackingGroup = stackingGroupsById[stackingGroupId];
        var bbox = new base.BBox2();
        stackingGroup.forEach(function(q) { bbox.addQuad(q); });
        var bboxRect = bbox.asRect();

        var curView = this.contentContainer_.children[
            this.contentContainer_.children.length - 1];
        if (curView.region.rectIntersects(bboxRect))
          curView = appendNewQuadView();
        curView.region.rects.push(bboxRect);
        stackingGroup.forEach(function(q) {
          curView.pendingQuads.push(q);
        });
      }

      for (var i = 0; i < this.contentContainer_.children.length; i++) {
        var child = this.contentContainer_.children[i];
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
      window.cancelAnimationFrame(this.rAF_);
      var _this = this;
      this.rAF_ = window.requestAnimationFrame(function(timestamp) {
        // set depth of each layer appropriately spaced apart
        var layers = _this.contentContainer_.children;
        for (var i = 0, len = layers.length; i < len; i++) {
          var layer = layers[i];
          // translate out by the value of the depth, but center around 0
          var newDepth = (_this.depth_ * (i - 0.5 * len)) *
              _this.matrixParameters_.depthRatio;
          layer.style.webkitTransform = 'translateZ(' + newDepth + 'px)';
        }

        // set rotation matrix to whatever is stored
        var transformString = '';
        transformString += 'rotateX(' + _this.rotations_.x + 'deg)';
        transformString += ' rotateY(' + _this.rotations_.y + 'deg)';
        _this.contentContainer_.style.webkitTransform = transformString;
      });
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
          this.matrixParameters_.strengthRatio;
      this.rotations_.y = this.rotationStart_.y + -delta.x *
          this.matrixParameters_.strengthRatio;
      this.repaint_();
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
