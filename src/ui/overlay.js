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
base.requireTemplate('ui.overlay');

base.require('base.utils');
base.require('base.properties');
base.require('base.events');
base.require('ui');

base.exportTo('ui', function() {
  /**
   * Creates a new overlay element. It will not be visible until shown.
   * @constructor
   * @extends {HTMLDivElement}
   */
  var Overlay = ui.define('overlay');

  Overlay.prototype = {
    __proto__: HTMLDivElement.prototype,

    /**
     * Initializes the overlay element.
     */
    decorate: function() {
      this.classList.add('overlay');

      this.parentEl_ = this.ownerDocument.body;

      this.visible_ = false;
      this.userCanClose_ = true;

      this.onKeyDown_ = this.onKeyDown_.bind(this);
      this.onClick_ = this.onClick_.bind(this);
      this.onFocusIn_ = this.onFocusIn_.bind(this);
      this.onDocumentClick_ = this.onDocumentClick_.bind(this);
      this.onClose_ = this.onClose_.bind(this);

      this.addEventListener('visibleChange',
          ui.Overlay.prototype.onVisibleChange_.bind(this), true);

      // Setup the shadow root
      this.shadow_ = this.webkitCreateShadowRoot();
      this.shadow_.appendChild(base.instantiateTemplate('#overlay-template'));

      this.closeBtn_ = this.shadow_.querySelector('close-button');
      this.closeBtn_.addEventListener('click', this.onClose_);

      this.shadow_
          .querySelector('overlay-frame')
          .addEventListener('click', this.onClick_);

      this.observer_ = new WebKitMutationObserver(
          this.didButtonBarMutate_.bind(this));
      this.observer_.observe(this.shadow_.querySelector('button-bar'),
                             { childList: true });

      // title is a variable on regular HTMLElements. However, we want to
      // use it for something more useful.
      Object.defineProperty(
          this, 'title', {
            get: function() {
              return this.shadow_.querySelector('title').textContent;
            },
            set: function(title) {
              this.shadow_.querySelector('title').textContent = title;
            }
          });
    },

    set userCanClose(userCanClose) {
      this.userCanClose_ = userCanClose;
      this.closeBtn_.style.display =
          userCanClose ? 'block' : 'none';
    },

    get leftButtons() {
      return this.shadow_.querySelector('left-buttons');
    },

    get rightButtons() {
      return this.shadow_.querySelector('right-buttons');
    },

    get visible() {
      return this.visible_;
    },

    set visible(newValue) {
      if (this.visible_ === newValue)
        return;

      base.setPropertyAndDispatchChange(this, 'visible', newValue);
    },

    onVisibleChange_: function() {
      this.visible_ ? this.show_() : this.hide_();
    },

    show_: function() {
      this.parentEl_.appendChild(this);

      if (this.userCanClose_) {
        document.addEventListener('keydown', this.onKeyDown_);
        document.addEventListener('click', this.onDocumentClick_);
      }

      this.parentEl_.addEventListener('focusin', this.onFocusIn_);
      this.tabIndex = 0;

      // Focus the first thing we find that makes sense. (Skip the close button
      // as it doesn't make sense as the first thing to focus.)
      var focusEl = undefined;
      var elList = this.querySelectorAll('button, input, list, select, a');
      if (elList.length > 0) {
        if (elList[0] === this.closeBtn_) {
          if (elList.length > 1)
            focusEl = elList[1];
        } else {
          focusEl = elList[0];
        }
      }
      if (focusEl === undefined)
        focusEl = this;
      focusEl.focus();
    },

    hide_: function() {
      this.parentEl_.removeChild(this);

      this.parentEl_.removeEventListener('focusin', this.onFocusIn_);

      if (this.closeBtn_)
        this.closeBtn_.removeEventListener(this.onClose_);

      document.removeEventListener('keydown', this.onKeyDown_);
      document.removeEventListener('click', this.onDocumentClick_);
    },

    onClose_: function(e) {
      this.visible = false;
      e.stopPropagation();
      e.preventDefault();
    },

    onFocusIn_: function(e) {
      if (e.target === this)
        return;

      window.setTimeout(function() { this.focus(); }, 0);
      e.preventDefault();
      e.stopPropagation();
    },

    didButtonBarMutate_: function(e) {
      var hasButtons = this.leftButtons.children.length +
          this.rightButtons.children.length > 0;
      if (hasButtons)
        this.shadow_.querySelector('button-bar').style.display = undefined;
      else
        this.shadow_.querySelector('button-bar').style.display = 'none';
    },

    onKeyDown_: function(e) {
      // Disallow shift-tab back to another element.
      if (e.keyCode === 9 &&  // tab
          e.shiftKey &&
          e.target === this) {
        e.preventDefault();
        return;
      }

      if (e.keyCode !== 27)  // escape
        return;

      this.visible = false;
      e.preventDefault();
    },

    onClick_: function(e) {
      e.stopPropagation();
    },

    onDocumentClick_: function(e) {
      if (!this.userCanClose_)
        return;

      this.visible = false;
      e.preventDefault();
      e.stopPropagation();
    }
  };

  return {
    Overlay: Overlay
  };
});
