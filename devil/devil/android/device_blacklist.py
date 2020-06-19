# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from devil.android import device_denylist

# TODO(crbug.com/1097306): Remove this (and this file) once existing uses
# have switched to using device_denylist directly.
Blacklist = device_denylist.Denylist
