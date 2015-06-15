// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.


/**
 * @fileoverview Boostrap for loading javascript/html files using d8_runner.
 */


/**
 * Defines the <%search-path%> for looking up relative path loading.
 * d8_runner.py will replace this with the actual search path.
 */
os.chdir('<%search-path%>');


/**
 * Load a HTML file, which absolute path or path relative to <%search-path%>.
 * Unlike the native load() method of d8, variables declared in |file_path|
 * will not be hoisted to the caller environment. For example:
 *
 * a.html:
 * <script>
 *   var x = 1;
 * </script>
 *
 * test.js:
 * loadHTML("a.html");
 * print(x);  // <- ReferenceError is thrown because x is not defined.
 *
 * @param {string} file_path path to the HTML file to be loaded.
 */
function loadHTML(file_path) {
  // TODO(nednguyen): Use a javascript html parser instead of relying on python
  // file for parsing HTML.
  // (https://github.com/google/trace-viewer/issues/1030)
  var stripped_js = os.system('python', ['<%html2jseval-path%>', file_path]);
  stripped_js = '//@ sourceURL=' + file_path + '\n' + stripped_js;
  eval(stripped_js);
}

var headless_global = this;
