// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('ui.info_bar');
base.require('ui');
base.require('ui.dom_helpers');

base.exportTo('ui', function() {
  /**
   * @constructor
   */
  var InfoBar = ui.define('info-bar');

  InfoBar.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.messageEl_ = ui.createSpan({className: 'message'});
      this.buttonsEl_ = ui.createSpan({className: 'buttons'});

      this.appendChild(this.messageEl_);
      this.appendChild(this.buttonsEl_);
      this.message = '';
      this.visible = false;
    },

    get message() {
      return this.messageEl_.textContent;
    },

    set message(message) {
      this.messageEl_.textContent = message;
    },

    get visible() {
      return this.classList.contains('info-bar-hidden');
    },

    set visible(visible) {
      if (visible)
        this.classList.remove('info-bar-hidden');
      else
        this.classList.add('info-bar-hidden');
    },

    removeAllButtons: function() {
      this.buttonsEl_.textContent = '';
    },

    addButton: function(text, clickCallback) {
      var button = document.createElement('button');
      button.textContent = text;
      button.addEventListener('click', clickCallback);
      this.buttonsEl_.appendChild(button);
      return button;
    }
  };

  return {
    InfoBar: InfoBar
  };
});
