// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * @fileoverview Base class for linux perf event parsers.
 */
base.defineModule('linux_perf_parser')
  .dependsOn('linux_perf_importer')
  .exportsTo('tracing', function() {

  /**
   * Parses linux perf events.
   * @constructor
   */
  function LinuxPerfParser(importer) {
    this.importer = importer;
  }

  LinuxPerfParser.prototype = {
    __proto__: Object.prototype,
  };

  return {
    LinuxPerfParser: LinuxPerfParser
  };

});
