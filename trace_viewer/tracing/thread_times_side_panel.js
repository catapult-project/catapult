// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.timeline_view_side_panel');

tvcm.exportTo('tracing', function() {
  /**
   * @constructor
   */
  var ThreadTimesSidePanel = tvcm.ui.define('x-thread-times-side-panel',
                                            tracing.TimelineViewSidePanel);
  ThreadTimesSidePanel.textLabel = 'Thread Times';
  ThreadTimesSidePanel.supportsModel = function(m) {
    return {
      supported: true
    };
  };

  ThreadTimesSidePanel.prototype = {
    __proto__: tracing.TimelineViewSidePanel.prototype,

    decorate: function() {
      this.textContent = 'Work in progress';
      this.style.width = '300px';
    }
  };

  tracing.TimelineViewSidePanel.registerPanelSubtype(ThreadTimesSidePanel);

  return {
    ThreadTimesSidePanel: ThreadTimesSidePanel
  };
});
