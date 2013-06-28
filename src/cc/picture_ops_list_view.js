// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('cc.picture_ops_list_view');

base.require('cc.constants');
base.require('cc.selection');
base.require('ui.list_view');
base.require('ui.dom_helpers');

base.exportTo('cc', function() {
  var constants = cc.constants;

  /**
   * @constructor
   */
  var PictureOpsListView = ui.define('picture-ops-list-view');

  PictureOpsListView.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.opsList_ = new ui.ListView();
      this.appendChild(this.opsList_);
      this.picture_ = undefined;
    },

    get picture() {
      return this.picture_;
    },

    set picture(picture) {
      this.picture_ = picture;
      this.updateContents_();
    },

    updateContents_: function() {
      this.opsList_.clear();

      var ops = this.picture_.getOps();
      if (!ops)
        return;

      ops.forEach(function(op) {
        var item = document.createElement('div');
        item.textContent = op.cmd_string;

        op.info.forEach(function(info) {
          var infoItem = document.createElement('div');
          infoItem.textContent = info;
          item.appendChild(infoItem);
        });

        this.opsList_.appendChild(item);
      }, this);
    }
  };

  return {
    PictureOpsListView: PictureOpsListView
  };
});
