/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

const path = require('path');

const {
  WEBPACK_OUTPUT_PATH: outputPath,
  WEBPACK_NODE_MODULES: nodeModules,
  WEBPACK_THIRD_PARTY: thirdParty,
} = process.env;

module.exports = {
  entry: {
    'service-worker': path.resolve(__dirname, 'service-worker.js'),
  },
  output: {
    filename: '[name].js',
    path: outputPath,
  },
  optimization: {
    minimizer: [],
  },
  resolve: {
    modules: [thirdParty],
    alias: {
      '/idb/idb.js': path.resolve(thirdParty, 'idb', 'idb.js'),
      '/tsmon_client/tsmon-client.js': path.resolve(
          thirdParty, 'tsmon_client', 'tsmon-client.js'),
    },
  },
  resolveLoader: {
    modules: [nodeModules],
  },
  mode: 'production',
};
