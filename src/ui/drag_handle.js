// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

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
      this.lastMousePos = 0;
      this.onMouseMove_ = this.onMouseMove_.bind(this);
      this.onMouseUp_ = this.onMouseUp_.bind(this);
      this.addEventListener('mousedown', this.onMouseDown_);
      this.target = undefined;
      this.horizontal = true;
    },

    get horizontal() {
      return this.horizontal_;
    },

    set horizontal(h) {
      this.horizontal_ = h;
      if (this.horizontal_)
        this.className = 'horizontal-drag-handle';
      else
        this.className = 'vertical-drag-handle';
    },

    get vertical() {
      return !this.horizontal_;
    },

    set vertical(v) {
      this.horizontal = !v;
    },

    onMouseMove_: function(e) {
      // Compute the difference in height position.
      var curMousePos = this.horizontal_ ? e.clientY : e.clientX;
      var delta = this.lastMousePos - curMousePos;
      var targetKey = this.horizontal_ ? 'height' : 'width';

      // If style is not set, start off with computed height.
      if (!this.target.style[targetKey]) {
        this.target.style[targetKey] =
            window.getComputedStyle(this.target)[targetKey];
      }

      // Apply new size to the container.
      if (this.target == this.nextSibling) {
        this.target.style[targetKey] =
            parseInt(this.target.style[targetKey]) + delta + 'px';
      } else {
        if (this.target != this.previousSibling)
          throw Error('Must be next sibling');
        this.target.style[targetKey] =
            parseInt(this.target.style[targetKey]) - delta + 'px';
      }


      this.lastMousePos = curMousePos;
      e.preventDefault();
      return true;
    },

    onMouseDown_: function(e) {
      if (!this.target)
        return;
      this.lastMousePos = this.horizontal_ ? e.clientY : e.clientX;
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
