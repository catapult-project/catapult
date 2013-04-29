// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Model is a parsed representation of the
 * TraceEvents obtained from base/trace_event in which the begin-end
 * tokens are converted into a hierarchy of processes, threads,
 * subrows, and slices.
 *
 * The building block of the model is a slice. A slice is roughly
 * equivalent to function call executing on a specific thread. As a
 * result, slices may have one or more subslices.
 *
 * A thread contains one or more subrows of slices. Row 0 corresponds to
 * the "root" slices, e.g. the topmost slices. Row 1 contains slices that
 * are nested 1 deep in the stack, and so on. We use these subrows to draw
 * nesting tasks.
 *
 */
'use strict';
base.exportTo('tracing', function() {

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
