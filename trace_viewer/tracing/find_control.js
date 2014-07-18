// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview FindControl.
 */
tvcm.requireTemplate('tracing.find_control');

tvcm.require('tracing.find_controller');
tvcm.require('tracing.timeline_track_view');

tvcm.exportTo('tracing', function() {

  /**
   * FindControl
   * @constructor
   */
  var FindControl = tvcm.ui.define('find-control');

  FindControl.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      var createShadowRoot = this.createShadowRoot ||
          this.webkitCreateShadowRoot;
      var shadow = createShadowRoot.call(this);

      shadow.appendChild(tvcm.instantiateTemplate('#find-control-template'));

      this.hitCountEl_ = shadow.querySelector('.hit-count-label');

      shadow.querySelector('.find-previous')
          .addEventListener('click', this.findPrevious_.bind(this));

      shadow.querySelector('.find-next')
          .addEventListener('click', this.findNext_.bind(this));

      this.filterEl_ = shadow.querySelector('#find-control-filter');
      this.filterEl_.addEventListener('input',
          this.filterTextChanged_.bind(this));

      this.filterEl_.addEventListener('keydown', function(e) {
        e.stopPropagation();
        if (e.keyCode == 13) {
          if (e.shiftKey)
            this.findPrevious_();
          else
            this.findNext_();
        }
      }.bind(this));

      this.filterEl_.addEventListener('keypress', function(e) {
        e.stopPropagation();
      });

      this.filterEl_.addEventListener('blur', function(e) {
        this.updateHitCountEl_();
      }.bind(this));

      this.filterEl_.addEventListener('focus', function(e) {
        this.controller.reset();
        this.filterTextChanged_();
        this.filterEl_.select();
      }.bind(this));

      // Prevent that the input text is deselected after focusing the find
      // control with the mouse.
      this.filterEl_.addEventListener('mouseup', function(e) {
        e.preventDefault();
      });

      this.updateHitCountEl_();
    },

    get controller() {
      return this.controller_;
    },

    set controller(c) {
      this.controller_ = c;
      this.updateHitCountEl_();
    },

    focus: function() {
      this.filterEl_.focus();
    },

    hasFocus: function() {
      return this === document.activeElement;
    },

    filterTextChanged_: function() {
      this.controller.filterText = this.filterEl_.value;
      this.updateHitCountEl_();
    },

    findNext_: function() {
      if (this.controller)
        this.controller.findNext();
      this.updateHitCountEl_();
    },

    findPrevious_: function() {
      if (this.controller)
        this.controller.findPrevious();
      this.updateHitCountEl_();
    },

    updateHitCountEl_: function() {
      if (!this.controller || !this.hasFocus()) {
        this.hitCountEl_.textContent = '';
        return;
      }
      var i = this.controller.currentHitIndex;
      var n = this.controller.filterHits.length;
      if (n == 0)
        this.hitCountEl_.textContent = '0 of 0';
      else
        this.hitCountEl_.textContent = (i + 1) + ' of ' + n;
    }
  };

  return {
    FindControl: FindControl
  };
});
