// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tvcm.base64');

tvcm.unittest.testSuite('tvcm.base64_test', function() {

  test('getDecodedLength', function() {
    assertTrue(tvcm.Base64.getDecodedBufferLength('YQ==') >= 1);
    assertTrue(tvcm.Base64.getDecodedBufferLength('YWJjZA==') >= 4);
    assertTrue(tvcm.Base64.getDecodedBufferLength('YWJjZGVm') >= 6);
  });

  test('DecodeToTypedArray', function() {
    var buffer = new DataView(new ArrayBuffer(256));
    tvcm.Base64.DecodeToTypedArray('YQ==', buffer);
    assertTrue(buffer.getInt8(0) == 97);

    tvcm.Base64.DecodeToTypedArray('YWJjZA==', buffer);
    for (var i = 0; i < 4; i++)
      assertTrue(buffer.getInt8(i) == 97 + i);

    tvcm.Base64.DecodeToTypedArray('YWJjZGVm', buffer);
    for (var i = 0; i < 4; i++)
      assertTrue(buffer.getInt8(i) == 97 + i);
  });

});
