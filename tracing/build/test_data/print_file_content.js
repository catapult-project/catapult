// Copyright (c) 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

if (arguments.length != 1) {
  throw 'arguments must be a single file name';
}

file_path = arguments[0];
file_content = read(file_path);
print('Content of file ' + file_path + ' is ' + file_content);
