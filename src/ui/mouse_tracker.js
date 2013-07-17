// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview A Mouse-event abtraction that waits for
 *   mousedown, then watches for subsequent mousemove events
 *   until the next mouseup event, then waits again.
 *   State changes are signaled with
 *      'mouse-tracker-start' : mousedown and tracking
 *      'mouse-tracker-move' : mouse move
 *      'mouse-tracker-end' : mouseup and not tracking.
 */

base.exportTo('ui', function() {

  /**
   * @constructor
   * @param {HTMLElement} targetElement will recv events 'mouse-tracker-start',
   *     'mouse-tracker-move', 'mouse-tracker-end'.
   */
  function MouseTracker(targetElement) {
    this.targetElement_ = targetElement;

    this.onMouseDown_ = this.onMouseDown_.bind(this);
    this.onMouseMove_ = this.onMouseMove_.bind(this);
    this.onMouseUp_ = this.onMouseUp_.bind(this);

    this.targetElement_.addEventListener('mousedown', this.onMouseDown_);
  }

  MouseTracker.prototype = {

    onMouseDown_: function(e) {
      if (e.button !== 0)
        return true;

      e = this.remakeEvent_(e, 'mouse-tracker-start');
      this.targetElement_.dispatchEvent(e);
      document.addEventListener('mousemove', this.onMouseMove_);
      document.addEventListener('mouseup', this.onMouseUp_);
      this.targetElement_.addEventListener('blur', this.onMouseUp_);
      this.savePreviousUserSelect_ = document.body.style['-webkit-user-select'];
      document.body.style['-webkit-user-select'] = 'none';
      e.preventDefault();
      return true;
    },

    onMouseMove_: function(e) {
      e = this.remakeEvent_(e, 'mouse-tracker-move');
      this.targetElement_.dispatchEvent(e);
    },

    onMouseUp_: function(e) {
      document.removeEventListener('mousemove', this.onMouseMove_);
      document.removeEventListener('mouseup', this.onMouseUp_);
      this.targetElement_.removeEventListener('blur', this.onMouseUp_);
      document.body.style['-webkit-user-select'] =
          this.savePreviousUserSelect_;
      e = this.remakeEvent_(e, 'mouse-tracker-end');
      this.targetElement_.dispatchEvent(e);
    },

    remakeEvent_: function(e, newType) {
      var remade = new base.Event(newType, true, true);
      remade.x = e.x;
      remade.y = e.y;
      remade.offsetX = e.offsetX;
      remade.offsetY = e.offsetY;
      remade.clientX = e.clientX;
      remade.clientY = e.clientY;
      return remade;
    }

  };

  return {
    MouseTracker: MouseTracker
  };
});
