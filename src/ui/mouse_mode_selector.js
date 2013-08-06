// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('ui.tool_button');
base.requireStylesheet('ui.mouse_mode_selector');

base.requireTemplate('ui.mouse_mode_selector');

base.require('base.events');
base.require('tracing.constants');
base.require('base.utils');
base.require('ui');
base.require('ui.mouse_tracker');

base.exportTo('ui', function() {

  var MOUSE_SELECTOR_MODE = {};
  MOUSE_SELECTOR_MODE.SELECTION = 0x1;
  MOUSE_SELECTOR_MODE.PANSCAN = 0x2;
  MOUSE_SELECTOR_MODE.ZOOM = 0x4;
  MOUSE_SELECTOR_MODE.TIMING = 0x8;
  MOUSE_SELECTOR_MODE.ALL_MODES = 0xF;

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

    decorate: function(opt_targetElement) {
      this.classList.add('mouse-mode-selector');

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

      this.initialRelativeMouseDownPos_ = {x: 0, y: 0};

      this.mousePos_ = {x: 0, y: 0};
      this.mouseDownPos_ = {x: 0, y: 0};

      this.dragHandleEl_.addEventListener('mousedown',
          this.onDragHandleMouseDown_.bind(this));
      window.addEventListener('resize',
          this.onWindowResize_.bind(this));

      this.onMouseDown_ = this.onMouseDown_.bind(this);
      this.onMouseMove_ = this.onMouseMove_.bind(this);
      this.onMouseUp_ = this.onMouseUp_.bind(this);

      this.buttonsEl_.addEventListener('mouseup', this.onButtonMouseUp_);
      this.buttonsEl_.addEventListener('mousedown', this.onButtonMouseDown_);
      this.buttonsEl_.addEventListener('click', this.onButtonPress_.bind(this));

      // TODO(nduca): Fix these,
      // https://code.google.com/p/trace-viewer/issues/detail?id=375.
      document.addEventListener('keypress', this.onKeyPress_.bind(this));
      document.addEventListener('keydown', this.onKeyDown_.bind(this));
      document.addEventListener('keyup', this.onKeyUp_.bind(this));

      var mode = base.Settings.get('mouse_mode_selector.mouseMode',
          MOUSE_SELECTOR_MODE.PANSCAN);
      // Modes changed from 1,2,3,4 to 0x1, 0x2, 0x4, 0x8. Fix any stray
      // settings to the best of our abilities.
      if (mode == 3) {
        mode = MOUSE_SELECTOR_MODE.ZOOM;
        base.Settings.set('mouse_mode_selector.mouseMode', mode);
      }
      this.mode = mode;

      this.supportedModeMask_ = MOUSE_SELECTOR_MODE.ALL_MODES;
      this.targetElement = opt_targetElement;
      this.isInTemporaryAlternativeMouseMode_ = false;
      this.isInteracting_ = false;
      this.isClick_ = false;
    },

    set targetElement(target) {
      if (this.targetElement_)
        this.targetElement_.removeEventListener('mousedown', this.onMouseDown_);
      this.targetElement_ = target;
      if (this.targetElement_)
        this.targetElement_.addEventListener('mousedown', this.onMouseDown_);
    },

    /**
     * Sets the supported modes. Should be an OR-ing of MOUSE_SELECTOR_MODE
     * values.
     */
    set supportedModeMask(supportedModeMask) {
      this.supportedModeMask_ = supportedModeMask;
      // TODO(nduca): Implement this.
    },

    get supportedModeMask() {
      return this.supportedModeMask_;
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

      this.currentMode_ = newMode;
      this.panScanModeButton_.classList.remove('active');
      this.selectionModeButton_.classList.remove('active');
      this.zoomModeButton_.classList.remove('active');
      this.timingModeButton_.classList.remove('active');

      switch (newMode) {

        case MOUSE_SELECTOR_MODE.PANSCAN:
          this.panScanModeButton_.classList.add('active');
          break;

        case MOUSE_SELECTOR_MODE.SELECTION:
          this.selectionModeButton_.classList.add('active');
          break;

        case MOUSE_SELECTOR_MODE.ZOOM:
          this.zoomModeButton_.classList.add('active');
          break;

        case MOUSE_SELECTOR_MODE.TIMING:
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
      var modeEventNames = {
        enter: '',
        begin: '',
        update: '',
        end: '',
        exit: ''
      };

      switch (mode) {

        case MOUSE_SELECTOR_MODE.PANSCAN:
          modeEventNames.enter = 'enterpan';
          modeEventNames.begin = 'beginpan';
          modeEventNames.update = 'updatepan';
          modeEventNames.end = 'endpan';
          modeEventNames.exit = 'exitpan';
          break;

        case MOUSE_SELECTOR_MODE.SELECTION:
          modeEventNames.enter = 'enterselection';
          modeEventNames.begin = 'beginselection';
          modeEventNames.update = 'updateselection';
          modeEventNames.end = 'endselection';
          modeEventNames.exit = 'exitselection';
          break;

        case MOUSE_SELECTOR_MODE.ZOOM:
          modeEventNames.enter = 'enterzoom';
          modeEventNames.begin = 'beginzoom';
          modeEventNames.update = 'updatezoom';
          modeEventNames.end = 'endzoom';
          modeEventNames.exit = 'exitzoom';
          break;

        case MOUSE_SELECTOR_MODE.TIMING:
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
      ui.trackMouseMovesUntilMouseUp(this.onMouseMove_, this.onMouseUp_);
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
        this.mode = MOUSE_SELECTOR_MODE.PANSCAN;
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

      var newInteractionMode = MOUSE_SELECTOR_MODE.PANSCAN;

      switch (e.target) {
        case this.panScanModeButton_:
          this.mode = MOUSE_SELECTOR_MODE.PANSCAN;
          break;

        case this.selectionModeButton_:
          this.mode = MOUSE_SELECTOR_MODE.SELECTION;
          break;

        case this.zoomModeButton_:
          this.mode = MOUSE_SELECTOR_MODE.ZOOM;
          break;

        case this.timingModeButton_:
          this.mode = MOUSE_SELECTOR_MODE.TIMING;
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

      switch (e.keyCode) {
        case 49:   // 1
          this.mode = MOUSE_SELECTOR_MODE.PANSCAN;
          break;
        case 50:   // 2
          this.mode = MOUSE_SELECTOR_MODE.SELECTION;
          break;
        case 51:   // 3
          this.mode = MOUSE_SELECTOR_MODE.ZOOM;
          break;
        case 52:   // 4
          this.mode = MOUSE_SELECTOR_MODE.TIMING;
          break;
      }
    },

    onKeyDown_: function(e) {

      // Prevent the user from changing modes during an interaction.
      if (this.isInteracting_)
        return;

      var userIsPressingCmdOrCtrl = (base.isMac && e.metaKey) ||
          (!base.isMac && e.ctrlKey);
      var userIsPressingShiftKey = e.shiftKey;

      if (this.mode !== MOUSE_SELECTOR_MODE.PANSCAN)
        return;

      if (userIsPressingCmdOrCtrl || userIsPressingShiftKey) {

        this.mode = userIsPressingCmdOrCtrl ?
            MOUSE_SELECTOR_MODE.ZOOM :
            MOUSE_SELECTOR_MODE.SELECTION;

        this.isInTemporaryAlternativeMouseMode_ = true;
        e.preventDefault();
      }
    },

    onKeyUp_: function(e) {

      // Prevent the user from changing modes during an interaction.
      if (this.isInteracting_)
        return;

      var userHasReleasedCmdOrCtrl = (base.isMac && !e.metaKey) ||
          (!base.isMac && !e.ctrlKey);
      var userHasReleasedShiftKey = e.shiftKey;

      if (this.isInTemporaryAlternativeMouseMode_ &&
          (userHasReleasedCmdOrCtrl || userHasReleasedShiftKey)) {
        this.mode = MOUSE_SELECTOR_MODE.PANSCAN;
      }

      this.isInTemporaryAlternativeMouseMode_ = false;

    },

    constrainPositionToWindowBounds_: function() {
      var parentRect = base.windowRectForElement(this.offsetParent);
      var top = 0;
      var bottom = parentRect.height - this.offsetHeight;
      var left = 0;
      var right = parentRect.width - this.offsetWidth;

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

      this.initialRelativeMouseDownPos_.x = e.clientX - this.offsetLeft;
      this.initialRelativeMouseDownPos_.y = e.clientY - this.offsetTop;
      ui.trackMouseMovesUntilMouseUp(this.onDragHandleMouseMove_.bind(this));
    },

    onDragHandleMouseMove_: function(e) {
      this.pos_.x = (e.clientX - this.initialRelativeMouseDownPos_.x);
      this.pos_.y = (e.clientY - this.initialRelativeMouseDownPos_.y);

      this.constrainPositionToWindowBounds_();
      this.updateStylesFromPosition_();
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
          MOUSE_SELECTOR_MODE.SELECTION);

      var mouseEvent = new base.Event(eventNames.begin, true, true);
      mouseEvent.data = e;
      this.dispatchEvent(mouseEvent);

      mouseEvent = new base.Event(eventNames.end, true, true);
      mouseEvent.data = e;
      this.dispatchEvent(mouseEvent);
    }
  };

  return {
    MouseModeSelector: MouseModeSelector,
    MOUSE_SELECTOR_MODE: MOUSE_SELECTOR_MODE
  };
});
