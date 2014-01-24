// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.exportTo('base', function() {

  var nextGUID = 1;
  var GUID = {
    allocate: function() {
      return nextGUID++;
    }
  };

  return {
    GUID: GUID
  };
});
