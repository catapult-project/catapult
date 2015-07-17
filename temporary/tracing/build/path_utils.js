// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
'use strict';

/**
 * @fileoverview Provides tools for working with paths, needed for d8
 * bootstrapping process.
 *
 * This file is pure js instead of an HTML imports module,
 * and writes to the global namespace so that it can
 * be included directly by the boostrap.
 */
(function(global) {
  global.PathUtils = {
    currentWorkingDirectory_: '/',

    get currentWorkingDirectory() {
      return this.currentWorkingDirectory_;
    },

    set currentWorkingDirectory(cwd) {
      if (!this.isAbs(cwd))
        throw new Error('nope');
      this.currentWorkingDirectory_ = this.normPath(cwd);
    },

    exists: function(fileName) {
      try {
        // Try a dummy read to check whether file_path exists.
        // TODO(nednguyen): find a more efficient way to check whether some file
        // path exists in d8.
        read(fileName);
        return true;
      } catch (err) {
        return false;
      }
    },

    isAbs: function(a) {
      return a[0] === '/';
    },

    join: function(a, b) {
      if (this.isAbs(b))
        return b;

      var res = a;
      if (!a.endsWith('/'))
        res += '/';

      res += b;
      return res;
    },

    normPath: function(a) {
      if (a.endsWith('/'))
        return a.substring(0, a.length - 1);
      return a;
    },

    absPath: function(a) {
      if (this.isAbs(a))
        return a;

      if (a.startsWith('./'))
        a = a.substring(2);
      var res = this.join(this.currentWorkingDirectory_, a);
      return this.normPath(res);
    },

    relPath: function(a, opt_relTo) {
      var a = this.absPath(a);

      var relTo;
      if (opt_relTo) {
        relTo = this.normPath(this.absPath(opt_relTo));
      } else {
        relTo = this.currentWorkingDirectory_;
      }

      if (relTo.endsWith('/'))
        relTo = relTo.substring(0, relTo.length - 1);

      if (!a.startsWith(relTo)) {
        var parts = relTo.substring(1).split('/');
        for (var i = 0; i < parts.length; i++)
          parts[i] = '..';
        var prefix = parts.join('/');

        var suffix;
        if (a.endsWith('/'))
          suffix = a.substring(0, a.length - 1);
        else
          suffix = a;
        return prefix + suffix;
      }

      var rest = a.substring(relTo.length + 1);
      if (rest.length === 0)
        return '.';
      return this.normPath(rest);
    }
  };
})(this);