// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('cc.picture');
base.require('cc.picture_debugger');

base.unittest.testSuite('cc.picture_debugger', function() {
  test('instantiate', function() {
    var picture = new cc.PictureSnapshot({id: '31415'}, 10, {
      'params': {
        'opaque_rect': [-15, -15, 0, 0],
        'layer_rect': [-15, -15, 46, 833]
      },
      'skp64': 'DAAAAHYEAADzAQAABwAAAAFkYWVy8AAAAAgAAB4DAAAADAAAIAAAgD8AAIA/CAAAHgMAAAAcAAADAAAAAAAAAAAAwI5EAID5QwEAAADoAAAACAAAHgMAAAAMAAAjAAAAAAAAAAAMAAAjAAAAAAAAAAAcAAADAAAAAAAAAAAAwI5EAID5QwEAAADkAAAAGAAAFQEAAAAAAAAAAAAAAADAjkQAgPlDGAAAFQIAAAAAAAAAAAAAAADAjkQAgPlDCAAAHgMAAAAcAAADAAAAAAAAAAAAwI5EAID5QwEAAADgAAAAGAAAFQMAAAAAAKBAAACgQAAAgEIAAIBCBAAAHAQAABwEAAAcBAAAHHRjYWYBAAAADVNrU3JjWGZlcm1vZGVjZnB0AAAAAHlhcmGgAAAAIHRucAMAAAAAAEBBAACAPwAAAAAAAIA/AAAAAAAAgEAAAP//ADABAAAAAAAAAEBBAACAPwAAAAAAAIA/AAAAAAAAgED/////AjABAAAAAAAAAAAAAAAAAAEAAAAEAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQEEAAIA/AAAAAAAAgD8AAAAAAACAQP8AAP8AMAEAAAAAACBmb2U=' // @suppress longLineCheck
    });
    picture.preInitialize();
    picture.initialize();

    var dbg = new cc.PictureDebugger();
    dbg.picture = picture;
    dbg.style.border = '1px solid black';
    this.addHTMLOutput(dbg);
  });
});
