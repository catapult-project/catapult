// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Implements an element that is hidden by default, but
 * when shown, dims and (attempts to) disable the main document.
 *
 * You can turn any div into an overlay. Note that while an
 * overlay element is shown, its parent is changed. Hiding the overlay
 * restores its original parentage.
 *
 */
base.requireStylesheet('ui.overlay');

base.require('base.properties');
base.require('base.events');
base.require('ui');

base.exportTo('ui', function() {
  /**
   * Manages a full-window div that darkens the window, disables
   * input, and hosts the currently-visible overlays. You shouldn't
   * have to instantiate this directly --- it gets set automatically.
   * @param {Object=} opt_propertyBag Optional properties.
   * @constructor
   * @extends {HTMLDivElement}
   */
  var OverlayRoot = ui.define('div');
  OverlayRoot.prototype = {
    __proto__: HTMLDivElement.prototype,
    decorate: function() {
      this.classList.add('overlay-root');


      this.createToolBar_();

      this.contentHost = this.ownerDocument.createElement('div');
      this.contentHost.classList.add('content-host');

      this.tabCatcher = this.ownerDocument.createElement('span');
      this.tabCatcher.tabIndex = 0;

      this.appendChild(this.contentHost);

      this.onKeydown_ = this.onKeydown_.bind(this);
      this.onFocusIn_ = this.onFocusIn_.bind(this);
      this.addEventListener('mousedown', this.onMousedown_.bind(this));
    },

    toggleToolbar: function(show) {
      if (show) {
        if (this.contentHost.firstChild)
          this.contentHost.insertBefore(this.contentHost.firstChild,
                                        this.toolbar_);
        else
          this.contentHost.appendChild(this.toolbar_);
      } else {
        if (this.toolbar_.parentElement)
          this.contentHost.removeChild(this.toolbar_);
      }
    },

    createToolBar_: function() {
      this.toolbar_ = this.ownerDocument.createElement('div');
      this.toolbar_.className = 'tool-bar';
      this.exitButton_ = this.ownerDocument.createElement('span');
      this.exitButton_.className = 'exit-button';
      this.exitButton_.textContent = 'x';
      this.exitButton_.title = 'Close Overlay (esc)';
      this.toolbar_.appendChild(this.exitButton_);
    },

    /**
     * Adds an overlay, attaching it to the contentHost so that it is visible.
     */
    showOverlay: function(overlay) {
      // Reparent this to the overlay content host.
      overlay.oldParent_ = overlay.parentNode;
      this.contentHost.appendChild(overlay);
      this.contentHost.appendChild(this.tabCatcher);

      // Show the overlay root.
      this.ownerDocument.body.classList.add('disabled-by-overlay');

      // Bring overlay into focus.
      overlay.tabIndex = 0;
      var focusElement =
          overlay.querySelector('button, input, list, select, a');
      if (!focusElement) {
        focusElement = overlay;
      }
      focusElement.focus();

      // Listen to key and focus events to prevent focus from
      // leaving the overlay.
      this.ownerDocument.addEventListener('focusin', this.onFocusIn_, true);
      overlay.addEventListener('keydown', this.onKeydown_);
    },

    /**
     * Clicking outside of the overlay will de-focus the overlay. The
     * next tab will look at the entire document to determine the focus.
     * For certain documents, this can cause focus to "leak" outside of
     * the overlay.
     */
    onMousedown_: function(e) {
      if (e.target == this) {
        e.preventDefault();
      }
    },

    /**
     * Prevents forward-tabbing out of the overlay
     */
    onFocusIn_: function(e) {
      if (e.target == this.tabCatcher) {
        window.setTimeout(this.focusOverlay_.bind(this), 0);
      }
    },

    focusOverlay_: function() {
      this.contentHost.firstChild.focus();
    },

    /**
     * Prevent the user from shift-tabbing backwards out of the overlay.
     */
    onKeydown_: function(e) {
      if (e.keyCode == 9 &&  // tab
          e.shiftKey &&
          e.target == this.contentHost.firstChild) {
        e.preventDefault();
      }
    },

    /**
     * Hides an overlay, attaching it to its original parent if needed.
     */
    hideOverlay: function(overlay) {
      // hide the overlay root
      this.visible = false;
      this.ownerDocument.body.classList.remove('disabled-by-overlay');
      this.lastFocusOut_ = undefined;

      // put the overlay back on its previous parent
      overlay.parentNode.removeChild(this.tabCatcher);
      if (overlay.oldParent_) {
        overlay.oldParent_.appendChild(overlay);
        delete overlay.oldParent_;
      } else {
        this.contentHost.removeChild(overlay);
      }

      // remove listeners
      overlay.removeEventListener('keydown', this.onKeydown_);
      this.ownerDocument.removeEventListener('focusin', this.onFocusIn_);
    }
  };

  /**
   * Creates a new overlay element. It will not be visible until shown.
   * @param {Object=} opt_propertyBag Optional properties.
   * @constructor
   * @extends {HTMLDivElement}
   */
  var Overlay = ui.define('div');

  Overlay.prototype = {
    __proto__: HTMLDivElement.prototype,

    /**
     * Initializes the overlay element.
     */
    decorate: function() {
      // create the overlay root on this document if its not present
      if (!this.ownerDocument.querySelector('.overlay-root')) {
        var overlayRoot = this.ownerDocument.createElement('div');
        ui.decorate(overlayRoot, OverlayRoot);
        this.ownerDocument.body.appendChild(overlayRoot);
      }

      this.classList.add('overlay');
      this.visible_ = false;
      this.obeyCloseEvents = false;
      this.additionalCloseKeyCodes = [];
      this.onKeyDown = this.onKeyDown.bind(this);
      this.onKeyPress = this.onKeyPress.bind(this);
      this.onDocumentClick = this.onDocumentClick.bind(this);
      this.addEventListener('visibleChange',
          Overlay.prototype.onVisibleChange_.bind(this), true);
      this.obeyCloseEvents = true;
    },

    get visible() {
      return this.visible_;
    },

    set visible(newValue) {
      base.setPropertyAndDispatchChange(this, 'visible', newValue);
    },

    get obeyCloseEvents() {
      return this.obeyCloseEvents_;
    },

    set obeyCloseEvents(newValue) {
      base.setPropertyAndDispatchChange(this, 'obeyCloseEvents', newValue);
      var overlayRoot = this.ownerDocument.querySelector('.overlay-root');
      // Currently the toolbar only has the close button.
      overlayRoot.toggleToolbar(newValue);
    },

    get toolbar() {
      return this.ownerDocument.querySelector('.overlay-root .tool-bar');
    },

    onVisibleChange_: function() {
      var overlayRoot = this.ownerDocument.querySelector('.overlay-root');
      if (this.visible) {
        overlayRoot.setAttribute('visible', 'visible');
        overlayRoot.showOverlay(this);
        document.addEventListener('keydown', this.onKeyDown, true);
        document.addEventListener('keypress', this.onKeyPress, true);
        document.addEventListener('click', this.onDocumentClick, true);
      } else {
        overlayRoot.removeAttribute('visible');
        document.removeEventListener('keydown', this.onKeyDown, true);
        document.removeEventListener('keypress', this.onKeyPress, true);
        document.removeEventListener('click', this.onDocumentClick, true);
        overlayRoot.hideOverlay(this);
      }
    },

    onKeyDown: function(e) {
      if (!this.obeyCloseEvents)
        return;

      if (e.keyCode == 27) {  // escape
        this.visible = false;
        e.preventDefault();
        return;
      }
    },

    onKeyPress: function(e) {
      if (!this.obeyCloseEvents)
        return;

      for (var i = 0; i < this.additionalCloseKeyCodes.length; i++) {
        if (e.keyCode == this.additionalCloseKeyCodes[i]) {
          this.visible = false;
          e.preventDefault();
          return;
        }
      }
    },

    onDocumentClick: function(e) {
      if (!this.obeyCloseEvents)
        return;
      var target = e.target;
      while (target !== null) {
        if (target === this)
          return;
        target = target.parentNode;
      }
      this.visible = false;
      e.preventDefault();
      return;
    }

  };

  return {
    Overlay: Overlay
  };
});
