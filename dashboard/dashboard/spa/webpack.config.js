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
    'index': path.resolve(__dirname, 'index.js'),
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
      'symbol-observable': path.resolve(nodeModules, 'symbol-observable'),
      '@webcomponents': path.resolve(nodeModules, '@webcomponents'),
      '/@polymer': path.resolve(nodeModules, '@polymer'),
      '@polymer': path.resolve(nodeModules, '@polymer'),
      '/idb/idb.js': path.resolve(thirdParty, 'idb', 'idb.js'),
    },
  },
  resolveLoader: {
    modules: [nodeModules],
  },
  mode: 'production',
};
