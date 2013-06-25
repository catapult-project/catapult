// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.exportTo('tracing.analysis', function() {

  function StubAnalysisTable() {
    this.ownerDocument_ = document;
    this.nodes_ = [];
  }

  StubAnalysisTable.prototype = {
    __proto__: Object.protoype,

    get ownerDocument() {
      return this.ownerDocument_;
    },

    appendChild: function(node) {
      this.nodes_.push(node);
    },

    get lastNode() {
      return this.nodes_.pop();
    },

    get nodeCount() {
      return this.nodes_.length;
    }

  };

  return {
    StubAnalysisTable: StubAnalysisTable
  };
});

