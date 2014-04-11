// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.exportTo('tracing.trace_model', function() {
  function StackFrame(parentFrame, id, category, title, colorId) {
    if (id === undefined)
      throw new Error('id must be given');
    this.parentFrame_ = parentFrame;
    this.id = id;
    this.category = category || '';
    this.title = title;
    this.colorId = colorId;
    this.children = [];

    if (this.parentFrame_)
      this.parentFrame_.addChild(this);
  }

  StackFrame.prototype = {
    get parentFrame() {
      return this.parentFrame_;
    },

    set parentFrame(parentFrame) {
      if (this.parentFrame_)
        this.parentFrame_.removeChild(this);
      this.parentFrame_ = parentFrame;
      if (this.parentFrame_)
        this.parentFrame_.addChild(this);
    },

    addChild: function(child) {
      this.children.push(child);
    },

    removeChild: function(child) {
      var i = this.children.indexOf(child.id);
      if (i == -1)
        throw new Error('omg');
      this.children.splice(i, 1);
    },

    removeAllChildren: function() {
      for (var i = 0; i < this.children.length; i++)
        this.children[i].parentFrame_ = undefined;
      this.children.splice(0, this.children.length);
    },

    toJSON: function() {
      return {};
    }
  };

  return {
    StackFrame: StackFrame
  };
});
