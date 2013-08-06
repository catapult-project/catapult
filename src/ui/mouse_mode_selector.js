// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('ui.tool_button');
base.requireStylesheet('ui.mouse_mode_selector');

base.requireTemplate('ui.mouse_mode_selector');

base.require('base.events');
base.require('tracing.constants');
base.require('tracing.mouse_mode_constants');
base.require('ui');

base.exportTo('ui', function() {

  /**
   * Provides a panel for switching the interaction mode of the mouse.
   * It handles the user interaction and dispatches events for the various
   * modes.
   *
   * @constructor
   * @extends {HTMLDivElement}
   */
  var MouseModeSelector = ui.define('div');

  MouseModeSelector.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function(parentEl) {

      this.classList.add('mouse-mode-selector');
      this.parentEl_ = parentEl;

      var node = base.instantiateTemplate('#mouse-mode-selector-template');
      this.appendChild(node);

      this.buttonsEl_ = this.querySelector('.buttons');
      this.dragHandleEl_ = this.querySelector('.drag-handle');
      this.panScanModeButton_ =
          this.buttonsEl_.querySelector('.pan-scan-mode-button');
      this.selectionModeButton_ =
          this.buttonsEl_.querySelector('.selection-mode-button');
      this.zoomModeButton_ =
          this.buttonsEl_.querySelector('.zoom-mode-button');
      this.timingModeButton_ =
          this.buttonsEl_.querySelector('.timing-mode-button');

      this.pos_ = {
        x: base.Settings.get('mouse_mode_selector.x', window.innerWidth - 50),
        y: base.Settings.get('mouse_mode_selector.y', 100)
      };

      this.constrainPositionToWindowBounds_();
      this.updateStylesFromPosition_();

      this.isDraggingModeSelectorDragHandle_ = false;
      this.initialRelativeMouseDownPos_ = {x: 0, y: 0};

      this.mousePos_ = {x: 0, y: 0};
      this.mouseDownPos_ = {x: 0, y: 0};

      this.dragHandleEl_.addEventListener('mousedown',
          this.onDragHandleMouseDown_.bind(this));
      document.addEventListener('mousemove',
          this.onDragHandleMouseMove_.bind(this));
      document.addEventListener('mouseup',
          this.onDragHandleMouseUp_.bind(this));
      window.addEventListener('resize',
          this.onWindowResize_.bind(this));

      this.buttonsEl_.addEventListener('mouseup', this.onButtonMouseUp_);
      this.buttonsEl_.addEventListener('mousedown', this.onButtonMouseDown_);
      this.buttonsEl_.addEventListener('click', this.onButtonPress_.bind(this));

      document.addEventListener('mousemove', this.onMouseMove_.bind(this));
      document.addEventListener('mouseup', this.onMouseUp_.bind(this));
      this.parentEl_.addEventListener('mousedown',
          this.onMouseDown_.bind(this));

      document.addEventListener('keypress', this.onKeyPress_.bind(this));
      document.addEventListener('keydown', this.onKeyDown_.bind(this));
      document.addEventListener('keyup', this.onKeyUp_.bind(this));

      this.mode = base.Settings.get('mouse_mode_selector.mouseMode',
          tracing.mouseModeConstants.MOUSE_MODE_PANSCAN);

      this.isInTemporaryAlternativeMouseMode_ = false;
      this.isInteracting_ = false;
      this.isClick_ = false;
    },

    get mode() {
      return this.currentMode_;
    },

    set mode(newMode) {

      if (this.currentMode_ === newMode)
        return;

      var eventNames;
      if (this.currentMode_) {
        eventNames = this.getCurrentModeEventNames_();
        this.dispatchEvent(new base.Event(eventNames.exit, true, true));
      }

      var mouseModeConstants = tracing.mouseModeConstants;

      this.currentMode_ = newMode;
      this.panScanModeButton_.classList.remove('active');
      this.selectionModeButton_.classList.remove('active');
      this.zoomModeButton_.classList.remove('active');
      this.timingModeButton_.classList.remove('active');

      switch (newMode) {

        case mouseModeConstants.MOUSE_MODE_PANSCAN:
          this.panScanModeButton_.classList.add('active');
          break;

        case mouseModeConstants.MOUSE_MODE_SELECTION:
          this.selectionModeButton_.classList.add('active');
          break;

        case mouseModeConstants.MOUSE_MODE_ZOOM:
          this.zoomModeButton_.classList.add('active');
          break;

        case mouseModeConstants.MOUSE_MODE_TIMING:
          this.timingModeButton_.classList.add('active');
          break;

        default:
          throw new Error('Unknown selection mode: ' + newMode);
          break;
      }

      eventNames = this.getCurrentModeEventNames_();
      this.dispatchEvent(new base.Event(eventNames.enter, true, true));

      base.Settings.set('mouse_mode_selector.mouseMode', newMode);
    },

    getModeEventNames_: function(mode) {
      var mouseModeConstants = tracing.mouseModeConstants;
      var modeEventNames = {
        enter: '',
        begin: '',
        update: '',
        end: '',
        exit: ''
      };

      switch (mode) {

        case mouseModeConstants.MOUSE_MODE_PANSCAN:
          modeEventNames.enter = 'enterpan';
          modeEventNames.begin = 'beginpan';
          modeEventNames.update = 'updatepan';
          modeEventNames.end = 'endpan';
          modeEventNames.exit = 'exitpan';
          break;

        case mouseModeConstants.MOUSE_MODE_SELECTION:
          modeEventNames.enter = 'enterselection';
          modeEventNames.begin = 'beginselection';
          modeEventNames.update = 'updateselection';
          modeEventNames.end = 'endselection';
          modeEventNames.exit = 'exitselection';
          break;

        case mouseModeConstants.MOUSE_MODE_ZOOM:
          modeEventNames.enter = 'enterzoom';
          modeEventNames.begin = 'beginzoom';
          modeEventNames.update = 'updatezoom';
          modeEventNames.end = 'endzoom';
          modeEventNames.exit = 'exitzoom';
          break;

        case mouseModeConstants.MOUSE_MODE_TIMING:
          modeEventNames.enter = 'entertiming';
          modeEventNames.begin = 'begintiming';
          modeEventNames.update = 'updatetiming';
          modeEventNames.end = 'endtiming';
          modeEventNames.exit = 'exittiming';
          break;

        default:
          throw new Error('Unsupported interaction mode');
          break;
      }

      return modeEventNames;
    },

    getCurrentModeEventNames_: function() {
      return this.getModeEventNames_(this.mode);
    },

    setPositionFromEvent_: function(pos, e) {
      pos.x = e.clientX;
      pos.y = e.clientY;
    },

    onMouseDown_: function(e) {
      if (e.button !== tracing.constants.LEFT_MOUSE_BUTTON)
        return;

      this.setPositionFromEvent_(this.mouseDownPos_, e);
      var eventNames = this.getCurrentModeEventNames_();
      var mouseEvent = new base.Event(eventNames.begin, true, true);
      mouseEvent.data = e;
      this.dispatchEvent(mouseEvent);
      this.isInteracting_ = true;
      this.isClick_ = true;
    },

    onMouseMove_: function(e) {
      this.setPositionFromEvent_(this.mousePos_, e);
      var eventNames = this.getCurrentModeEventNames_();
      var mouseEvent = new base.Event(eventNames.update, true, true);
      mouseEvent.data = e;
      this.dispatchEvent(mouseEvent);

      if (this.isInteracting_)
        this.checkIsClick_(e);
    },

    onMouseUp_: function(e) {
      if (e.button !== tracing.constants.LEFT_MOUSE_BUTTON)
        return;

      var eventNames = this.getCurrentModeEventNames_();
      var mouseEvent = new base.Event(eventNames.end, true, true);
      var userHasReleasedShiftKey = !e.shiftKey;
      var userHasReleasedCmdOrCtrl = (base.isMac && !e.metaKey) ||
          (!base.isMac && !e.ctrlKey);

      mouseEvent.data = e;
      mouseEvent.consumed = false;
      mouseEvent.isClick = this.isClick_;

      this.dispatchEvent(mouseEvent);

      if (this.isClick_ && !mouseEvent.consumed)
        this.dispatchClickEvents_(e);

      this.isInteracting_ = false;

      if (this.isInTemporaryAlternativeMouseMode_ && userHasReleasedShiftKey &&
          userHasReleasedCmdOrCtrl) {
        this.mode = tracing.mouseModeConstants.MOUSE_MODE_PANSCAN;
      }
    },

    onButtonMouseDown_: function(e) {
      e.preventDefault();
      e.stopImmediatePropagation();
    },

    onButtonMouseUp_: function(e) {
      e.preventDefault();
      e.stopImmediatePropagation();
    },

    onButtonPress_: function(e) {

      var mouseModeConstants = tracing.mouseModeConstants;
      var newInteractionMode = mouseModeConstants.MOUSE_MODE_PANSCAN;

      switch (e.target) {
        case this.panScanModeButton_:
          this.mode = mouseModeConstants.MOUSE_MODE_PANSCAN;
          break;

        case this.selectionModeButton_:
          this.mode = mouseModeConstants.MOUSE_MODE_SELECTION;
          break;

        case this.zoomModeButton_:
          this.mode = mouseModeConstants.MOUSE_MODE_ZOOM;
          break;

        case this.timingModeButton_:
          this.mode = mouseModeConstants.MOUSE_MODE_TIMING;
          break;

        default:
          throw new Error('Unknown mouse mode button pressed');
          break;
      }

      e.preventDefault();
      this.isInTemporaryAlternativeMouseMode_ = false;
    },

    onKeyPress_: function(e) {

      // Prevent the user from changing modes during an interaction.
      if (this.isInteracting_)
        return;

      var mouseModeConstants = tracing.mouseModeConstants;

      switch (e.keyCode) {
        case 49:   // 1
          this.mode = mouseModeConstants.MOUSE_MODE_PANSCAN;
          break;
        case 50:   // 2
          this.mode = mouseModeConstants.MOUSE_MODE_SELECTION;
          break;
        case 51:   // 3
          this.mode = mouseModeConstants.MOUSE_MODE_ZOOM;
          break;
        case 52:   // 4
          this.mode = mouseModeConstants.MOUSE_MODE_TIMING;
          break;
      }
    },

    onKeyDown_: function(e) {

      // Prevent the user from changing modes during an interaction.
      if (this.isInteracting_)
        return;

      var mouseModeConstants = tracing.mouseModeConstants;
      var userIsPressingCmdOrCtrl = (base.isMac && e.metaKey) ||
          (!base.isMac && e.ctrlKey);
      var userIsPressingShiftKey = e.shiftKey;

      if (this.mode !== mouseModeConstants.MOUSE_MODE_PANSCAN)
        return;

      if (userIsPressingCmdOrCtrl || userIsPressingShiftKey) {

        this.mode = userIsPressingCmdOrCtrl ?
            mouseModeConstants.MOUSE_MODE_ZOOM :
            mouseModeConstants.MOUSE_MODE_SELECTION;

        this.isInTemporaryAlternativeMouseMode_ = true;
        e.preventDefault();
      }
    },

    onKeyUp_: function(e) {

      // Prevent the user from changing modes during an interaction.
      if (this.isInteracting_)
        return;

      var mouseModeConstants = tracing.mouseModeConstants;
      var userHasReleasedCmdOrCtrl = (base.isMac && !e.metaKey) ||
          (!base.isMac && !e.ctrlKey);
      var userHasReleasedShiftKey = e.shiftKey;

      if (this.isInTemporaryAlternativeMouseMode_ &&
          (userHasReleasedCmdOrCtrl || userHasReleasedShiftKey)) {
        this.mode = mouseModeConstants.MOUSE_MODE_PANSCAN;
      }

      this.isInTemporaryAlternativeMouseMode_ = false;

    },

    constrainPositionToWindowBounds_: function() {
      var top = 0;
      var bottom = window.innerHeight - this.offsetHeight;
      var left = 0;
      var right = window.innerWidth - this.offsetWidth;

      this.pos_.x = Math.max(this.pos_.x, left);
      this.pos_.x = Math.min(this.pos_.x, right);

      this.pos_.y = Math.max(this.pos_.y, top);
      this.pos_.y = Math.min(this.pos_.y, bottom);
    },

    updateStylesFromPosition_: function() {
      this.style.left = this.pos_.x + 'px';
      this.style.top = this.pos_.y + 'px';

      base.Settings.set('mouse_mode_selector.x', this.pos_.x);
      base.Settings.set('mouse_mode_selector.y', this.pos_.y);
    },

    onDragHandleMouseDown_: function(e) {
      e.preventDefault();
      e.stopImmediatePropagation();

      this.isDraggingModeSelectorDragHandle_ = true;

      this.initialRelativeMouseDownPos_.x = e.clientX - this.offsetLeft;
      this.initialRelativeMouseDownPos_.y = e.clientY - this.offsetTop;

    },

    onDragHandleMouseMove_: function(e) {
      if (!this.isDraggingModeSelectorDragHandle_)
        return;

      this.pos_.x = (e.clientX - this.initialRelativeMouseDownPos_.x);
      this.pos_.y = (e.clientY - this.initialRelativeMouseDownPos_.y);

      this.constrainPositionToWindowBounds_();
      this.updateStylesFromPosition_();
    },

    onDragHandleMouseUp_: function(e) {
      this.isDraggingModeSelectorDragHandle_ = false;
    },

    onWindowResize_: function(e) {
      this.constrainPositionToWindowBounds_();
      this.updateStylesFromPosition_();
    },

    checkIsClick_: function(e) {
      if (!this.isInteracting_ || !this.isClick_)
        return;

      var deltaX = this.mousePos_.x - this.mouseDownPos_.x;
      var deltaY = this.mousePos_.y - this.mouseDownPos_.y;
      var minDist = tracing.constants.MIN_MOUSE_SELECTION_DISTANCE;

      if (deltaX * deltaX + deltaY * deltaY > minDist * minDist)
        this.isClick_ = false;
    },

    dispatchClickEvents_: function(e) {
      if (!this.isClick_)
        return;

      var eventNames = this.getModeEventNames_(
          tracing.mouseModeConstants.MOUSE_MODE_SELECTION);

      var mouseEvent = new base.Event(eventNames.begin, true, true);
      mouseEvent.data = e;
      this.dispatchEvent(mouseEvent);

      mouseEvent = new base.Event(eventNames.end, true, true);
      mouseEvent.data = e;
      this.dispatchEvent(mouseEvent);
    }
  };

  return {
    MouseModeSelector: MouseModeSelector
  };
});
