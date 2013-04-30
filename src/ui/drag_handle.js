/* Copyright (c) 2012 The Chromium Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */
'use strict';

base.require('ui');
base.requireStylesheet('ui.drag_handle');

base.exportTo('ui', function() {

  /**
   * Detects when user clicks handle determines new height of container based
   * on user's vertical mouse move and resizes the target.
   * @constructor
   * @extends {HTMLDivElement}
   * You will need to set target to be the draggable element
   */
  var DragHandle = ui.define('x-drag-handle');

  DragHandle.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.lastMousePosY = 0;
      this.onMouseMove_ = this.onMouseMove_.bind(this);
      this.onMouseUp_ = this.onMouseUp_.bind(this);
      this.addEventListener('mousedown', this.onMouseDown_);
      this.target = undefined;
    },

    onMouseMove_: function(e) {
      // Compute the difference in height position.
      var dy = this.lastMousePosY - e.clientY;
      // If style is not set, start off with computed height.
      if (!this.target.style.height)
        this.target.style.height = window.getComputedStyle(this.target).height;
      // Apply new height to the container.
      this.target.style.height = parseInt(this.target.style.height) + dy + 'px';
      this.lastMousePosY = e.clientY;
      e.preventDefault();
      return true;
    },

    onMouseDown_: function(e) {
      if (!this.target)
        return;
      this.lastMousePosY = e.clientY;
      document.addEventListener('mousemove', this.onMouseMove_);
      document.addEventListener('mouseup', this.onMouseUp_);
      e.preventDefault();
      return true;
    },

    onMouseUp_: function(e) {
      document.removeEventListener('mousemove', this.onMouseMove_);
      document.removeEventListener('mouseup', this.onMouseUp_);
      e.preventDefault();
    }
  };

  return {
    DragHandle: DragHandle
  };
});
