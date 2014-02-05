# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import sys

src_dir = os.path.join(os.path.dirname(__file__), '..')

sys.path.append(os.path.join(src_dir, 'third_party/python_gflags'))
sys.path.append(os.path.join(src_dir, 'third_party/closure_linter'))


from closure_linter import gjslint

def main():
  os.chdir(src_dir)
  if sys.argv[1:] == ['--help']:
    sys.exit(gjslint.main())

  if len(sys.argv) > 1:
    sys.stderr.write('No arguments allowed')
    sys.exit(1)
  sys.argv.append('--strict')
  sys.argv.append('--unix_mode')
  sys.argv.append('--check_html')
  sys.argv.extend(['-r', 'src/'])
  sys.argv.extend(['-r', 'third_party/tvcm/base/'])
  sys.argv.extend(['-r', 'third_party/tvcm/ui/'])
  gjslint.main()
