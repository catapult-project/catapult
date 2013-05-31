// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('ui.info_bar');
base.require('ui');

base.exportTo('ui', function() {
  /**
   * @constructor
   */
  var InfoBar = ui.define('info-bar');

  InfoBar.prototype = {
    __proto__: 'info-bar'.prototype,

    decorate: function() {
      this.message = '';
      this.visible = false;
    },

    get message() {
      return this.message_;
    },

    set message(message) {
      this.message_ = message;
      this.textContent = this.message_;
    },

    get visible() {
      return this.classList.contains('info-bar-hidden');
    },

    set visible(visible) {
      if (visible)
        this.classList.remove('info-bar-hidden');
      else
        this.classList.add('info-bar-hidden');
    }
  };

  return {
    InfoBar: InfoBar
  };
});
