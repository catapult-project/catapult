// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * @fileoverview Boostrap for loading javascript/html files using d8_runner.
 */
(function(global) {
  /* There are four ways a program can finish running in D8:
   * - a) Intentioned exit triggered via quit(0)
   * - b) Intentioned exit triggered via quit(n)
   * - c) Running to end of the script
   * - d) An uncaught exception
   *
   * The exit code of d8 for case a is 0.
   * The exit code of d8 for case b is unsigned(n) & 0xFF
   * The exit code of d8 for case c is 0.
   * The exit code of d8 for case d is 1.
   *
   * D8 runner needs to distinguish between these cases:
   * - a) _ExecuteFileWithD8 should return 0
   * - b) _ExecuteFileWithD8 should return n
   * - c) _ExecuteFileWithD8 should return 0
   * - d) _ExecuteFileWithD8 should raise an Exception
   *
   * The hard one here is d and b with n=1, because they fight for the same
   * return code.
   *
   * Our solution is to monkeypatch quit() s.t. quit(1) becomes exitcode=2.
   * This makes quit(255) disallowed, but it ensures that D8 runner is able
   * to handle the other cases correctly.
   */
  var realQuit = global.quit;
  global.quit = function(exitCode) {
    // Normalize the exit code.
    if (exitCode < 0) {
      exitCode = (exitCode % 256) + 256;
    } else {
      exitCode = exitCode % 256;
    }

    // 255 is reserved due to reasons noted above.
    if (exitCode == 255)
      throw new Error('exitCodes 255 is reserved, sorry.');
    if (exitCode === 0)
      realQuit(0);
    realQuit(exitCode + 1);
  }

  /**
   * Polyfills console's methods.
   */
  global.console = {
    log: function() {
      var args = Array.prototype.slice.call(arguments);
      print(args.join(' '));
    },

    info: function() {
      var args = Array.prototype.slice.call(arguments);
      print('Info:', args.join(' '));
    },

    error: function() {
      var args = Array.prototype.slice.call(arguments);
      print('Error:', args.join(' '));
    },

    warn: function() {
      var args = Array.prototype.slice.call(arguments);
      print('Warning:', args.join(' '));
    }
  };

  if (os.chdir) {
    os.chdir = function() {
      throw new Error('Dont do this');
    }
  }

  // Bring in path utils.
  load('<%path_utils_js_path%>');
  PathUtils.currentWorkingDirectory = '<%current_working_directory%>';

  /**
   * Strips the starting '/' in file_path if |file_path| is meant to be a
   * relative path.
   *
   * @param {string} file_path path to some file, can be relative or absolute
   * path.
   * @return {string} the file_path with starting '/' removed if |file_path|
   * does not exist or the original |file_path| otherwise.
   */
  function _stripStartingSlashIfNeeded(file_path) {
    if (file_path.substring(0, 1) !== '/') {
      return file_path;
    }
    if (PathUtils.exists(file_path))
      return file_path;
    return file_path.substring(1);
  }

  var sourcePaths = JSON.parse('<%source_paths%>');

  function hrefToAbsolutePath(href) {
    var pathPart;
    if (!PathUtils.isAbs(href)) {
      throw new Error('Found a non absolute import and thats not supported: ' +
                      href);
    } else {
      pathPart = href.substring(1);
    }

    candidates = [];
    for (var i = 0; i < sourcePaths.length; i++) {
      var candidate = PathUtils.join(sourcePaths[i], pathPart);
      if (PathUtils.exists(candidate))
        candidates.push(candidate);
    }
    if (candidates.length > 1)
      throw new Error('Multiple candidates found for ' + href);
    if (candidates.length === 0)
      throw new Error(href + ' not found!');
    return candidates[0];
  }

  var loadedModulesByFilePath = {};

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
  global.loadHTML = function(href) {
    // TODO(nednguyen): Use a javascript html parser instead of relying on
    // python file for parsing HTML.
    // (https://github.com/google/trace-viewer/issues/1030)
    var absPath = hrefToAbsolutePath(href);
    global.loadHTMLFile(absPath, href);
  };

  global.loadScript = function(href) {
    var absPath = hrefToAbsolutePath(href);
    global.loadFile(absPath, href);
  };

  global.loadHTMLFile = function(absPath, opt_href) {
    var href = opt_href || absPath;
    if (loadedModulesByFilePath[absPath])
      return;
    loadedModulesByFilePath[absPath] = true;


    try {
      var stripped_js = os.system('python', ['<%html2jseval-path%>', absPath]);
    } catch (err) {
      if (!PathUtils.exists(absPath))
        throw new Error('Error in loading ' + href + ': File does not exist');
      throw new Error('Error in loading ' + href + ': ' + err);
    }

    // Add "//@ sourceURL=|file_path|" to the end of generated js to preserve
    // the line numbers
    stripped_js = stripped_js + '\n//@ sourceURL=' + href;
    eval(stripped_js);
  };

  global.loadFile = function(absPath, opt_href) {
    var href = opt_href || absPath;
    var relPath = PathUtils.relPath(absPath);
    try {
      load(relPath);
    } catch (err) {
      throw new Error('Error in loading ' + href + ': ' + err);
    }
  };
})(this);