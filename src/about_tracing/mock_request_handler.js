// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.exportTo('about_tracing', function() {
  function MockRequestHandler() {
    this.requests = [];
    this.nextRequestIndex = 0;
    this.allowLooping = false;
  }

  MockRequestHandler.prototype = {
    expectRequest: function(method, pathRegex, generateResponse) {
      var generateResponseCb;
      if (typeof generateResponse === 'function') {
        generateResponseCb = generateResponse;
      } else {
        generateResponseCb = function() {
          return generateResponse;
        };
      }

      this.requests.push({
        method: method,
        pathRegex: pathRegex,
        generateResponseCb: generateResponseCb});
    },

    tracingRequest: function(method, path, data) {
      return new Promise(function(resolver) {
        var requestIndex = this.nextRequestIndex;
        if (requestIndex >= this.requests.length)
          throw new Error('Unhandled request');
        if (!this.allowLooping) {
          this.nextRequestIndex++;
        } else {
          this.nextRequestIndex = (this.nextRequestIndex + 1) %
              this.requests.length;
        }

        var req = this.requests[requestIndex];
        assertTrue(req.method === method);
        assertTrue(path.search(req.pathRegex) == 0);
        var resp = req.generateResponseCb(data, path);
        resolver.resolve(resp);
      }.bind(this));
    },

    assertAllRequestsHandled: function() {
      if (this.allowLooping)
        throw new Error('Incompatible with allowLooping');
      assertTrue(this.nextRequestIndex == this.requests.length);
    }
  };

  return {
    MockRequestHandler: MockRequestHandler
  };
});
