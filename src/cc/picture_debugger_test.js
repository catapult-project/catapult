// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

base.require('cc.picture');
base.require('cc.picture_debugger');

'use strict';

base.unittest.testSuite('cc.picture_debugger', function() {
  test('instantiate', function() {
    var picture = new cc.PictureSnapshot({id: '31415'}, 10, {
      'params': {
        'opaque_rect': [-15, -15, 0, 0],
        'layer_rect': [-15, -15, 46, 833]
      },
      'skp64': 'CwAAAC4AAABBAwAAAwAAAAFkYWVywAAAAAgAAB4DAAAACAAAHgMAAAAMAAAjAABwQQAAcEEcAAADAABwwQAAcMEAAPhBAIBMRAEAAAC4AAAADAAAIwAAAAAAAAAACAAAHgMAAAAMAAAjAMCXxAAAAAAIAAAeAwAAABwAAAMA4JVEAABwwQCgm0QAgExEAQAAALAAAAAMAAAjAMCXRAAAAAAIAAAeAwAAAAgAAAUBAAAAFAAABgAAAAAAAAAAAAAAAAAAAAAEAAAcBAAAHAQAABwEAAAcBAAAHHRjYWYAAAAAY2ZwdAAAAAB5YXJhLAEAAHBtdGIBAAAALgAAAEEDAAAAAAAA5QAAAIlQTkcNChoKAAAADUlIRFIAAAAuAAADQQgGAAAAn/OMJQAAAKxJREFUeJztwTEBAAAAwqD1T20JT6AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALgaWhcAAerJ2TMAAAAASUVORK5CYIIAAAB4cnRtAQAAAAAAgD8AAAAAAABwwQAAAAAAAIA/AABwwQAAAAAAAAAAAACAPyBmb2U=' // @suppress longLineCheck
    });
    picture.preInitialize();
    picture.initialize();

    var dbg = new cc.PictureDebugger();
    dbg.picture = picture;
    dbg.style.border = '1px solid black';
    this.addHTMLOutput(dbg);
  });
});
