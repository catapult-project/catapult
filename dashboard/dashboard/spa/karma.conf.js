/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

const path = require('path');

process.env.CHROME_BIN = require('puppeteer').executablePath();

const catapult = path.resolve('../../..');
const nodeModules = path.resolve(
    catapult, 'common/node_runner/node_runner/node_modules');
const thirdParty = path.resolve(catapult, 'third_party');
const tracing = path.resolve(catapult, 'tracing');

function serveRoot(pattern) {
  return {
    pattern, watched: false, included: false, served: true, nocache: false,
  };
}

module.exports = function(config) {
  const isDebug = process.argv.some((arg) => arg === '--debug');
  const coverage = process.argv.some((arg) => arg === '--coverage');
  config.set({
    basePath: '',

    client: {
      mocha: {
        reporter: 'html',
        ui: 'tdd',
      },
    },

    mochaReporter: {
      showDiff: true,
    },

    frameworks: ['mocha', 'sinon'],

    files: [
      'tests.js',
      serveRoot('../../**'),
      serveRoot('../../../third_party/polymer2/bower_components/**'),
      serveRoot('../../../tracing/tracing/**'),
      serveRoot('../../../tracing/third_party/gl-matrix/dist/**'),
      serveRoot('../../../third_party/polymer-svg-template/**'),
      serveRoot('../../../tracing/third_party/mannwhitneyu/**'),
    ],

    proxies: {
      '/dashboard/': path.resolve(catapult, 'dashboard/dashboard') + '/',
      '/bower_components/': path.resolve(
          thirdParty, 'polymer2/bower_components') + '/',
      '/tracing/': path.resolve(catapult, 'tracing/tracing') + '/',
      '/gl-matrix-min.js': path.resolve(
          catapult, 'tracing/third_party/gl-matrix/dist/gl-matrix-min.js'),
      '/mannwhitneyu/': path.resolve(
          catapult, 'tracing/third_party/mannwhitneyu') + '/',
      '/polymer-svg-template/': path.resolve(
          catapult, 'third_party/polymer-svg-template') + '/',
    },

    exclude: [],

    preprocessors: {
      'tests.js': ['webpack', 'sourcemap'],
    },

    plugins: [
      'karma-chrome-launcher',
      'karma-coverage',
      'karma-mocha',
      'karma-sinon',
      'karma-sourcemap-loader',
      'karma-webpack',
    ],

    webpack: {
      devtool: 'inline-source-map',
      mode: 'development',
      module: {
        rules: [
          {
            test: /\.js$/,
            loader: 'istanbul-instrumenter-loader',
            include: path.resolve('.'),
            exclude: [/\.test.js$/],
            query: {esModules: true},
          },
        ],
      },
      resolve: {
        modules: [
          nodeModules,
          thirdParty,
          path.resolve(thirdParty, 'polymer2'),
        ],
        alias: {
          'idb': path.resolve(thirdParty, 'idb', 'idb.js'),
          'dashboard-metrics': path.resolve(__dirname, '../static/metrics.js'),
        },
      },
      resolveLoader: {
        modules: [nodeModules],
      },
    },

    reporters: ['progress'].concat(coverage ? ['coverage'] : []),

    coverageReporter: {
      check: {
        global: {
          statements: 75,
          branches: 67,
          functions: 75,
          lines: 75,
        },
      },
      dir: 'coverage',
      reporters: [
        {type: 'lcovonly', subdir: '.'},
        {type: 'json', subdir: '.', file: 'coverage.json'},
        {type: 'html'},
        {type: 'text'},
      ],
    },

    port: 9876,

    colors: true,

    logLevel: config.LOG_INFO,

    autoWatch: true,

    browsers: isDebug ? ['Chrome_latest'] : ['ChromeHeadless'],

    customLaunchers: {
      Chrome_latest: {
        base: 'Chrome',
        version: 'latest',
      },
    },

    singleRun: isDebug ? false : true,

    concurrency: Infinity,
  });
};

