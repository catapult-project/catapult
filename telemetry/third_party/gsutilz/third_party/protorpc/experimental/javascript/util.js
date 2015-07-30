// Copyright 2011 Google Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

/**
 * @fileoverview Utilities for ProtoRpc.
 */

goog.provide('ProtoRpc.Util.Error');

goog.require('goog.debug.Error');
goog.require('goog.string');


/**
 * Base class for all ProtoRpc errors.
 * @param {string} pattern The pattern to use for the error message.
 * @param {!Array.<*>} args The items to substitue into the pattern.
 * @constructor
 * @extends {goog.debug.Error}
 */
ProtoRpc.Util.Error = function(pattern, args) {
  args.unshift(pattern);
  goog.base(this, goog.string.subs.apply(null, args));
};
goog.inherits(ProtoRpc.Util.Error, goog.debug.Error);


/**
 * Convert underscores and dashes to camelCase.
 * 
 * @param {string} str The string to camel case.
 * @param {string=} prefix An optional prefix.
 */
ProtoRpc.Util.toCamelCase = function(str, prefix) {
  if (prefix) {
    str = [prefix, '_', str].join('');
  }
  return str.replace(/[_|-]([a-z])/g, function(all, match) {
    return match.toUpperCase();
  });
};