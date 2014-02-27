// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.requireStylesheet('tvcm.ui.common');

/*
 * Here is where we bring in modules that are used in about:tracing UI only.
 */
tvcm.require('tracing.importer');
tvcm.require('cc');
tvcm.require('tcmalloc');
tvcm.require('system_stats');
tvcm.require('gpu');

tvcm.exportTo('about_tracing', function() {
  return {
  };
});
