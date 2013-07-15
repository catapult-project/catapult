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

      this.selectedOp_ = undefined;
      this.selectedOpIndex_ = undefined;
      this.opsList_.addEventListener(
          'selection-changed', this.onSelectionChanged_.bind(this));

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

      if (!this.picture_)
        return;

      var ops = this.picture_.getOps();
      if (!ops)
        return;

      for (var i = 0; i < ops.length; i++) {
        var op = ops[i];
        var item = document.createElement('div');
        item.textContent = i + ') ' + op.cmd_string;

        op.info.forEach(function(info) {
          var infoItem = document.createElement('div');
          infoItem.textContent = info;
          item.appendChild(infoItem);
        });

        this.opsList_.appendChild(item);
      }
    },

    onSelectionChanged_: function(e) {
      var beforeSelectedOp = true;

      // Deselect on re-selection.
      if (this.opsList_.selectedElement === this.selectedOp_) {
        this.opsList_.selectedElement = undefined;
        beforeSelectedOp = false;
        this.selectedOpIndex_ = undefined;
      }

      this.selectedOp_ = this.opsList_.selectedElement;

      // Set selection on all previous ops.
      var ops = this.opsList_.children;
      for (var i = 0; i < ops.length; i++) {
        var op = ops[i];
        if (op === this.selectedOp_) {
          beforeSelectedOp = false;
          this.selectedOpIndex_ = i;
        } else if (beforeSelectedOp) {
          op.setAttribute('beforeSelection', 'beforeSelection');
        } else {
          op.removeAttribute('beforeSelection');
        }
      }

      base.dispatchSimpleEvent(this, 'selection-changed', false);
    },

    get selectedOpIndex() {
      return this.selectedOpIndex_;
    }
  };

  return {
    PictureOpsListView: PictureOpsListView
  };
});
