<!-- Copyright 2015 The Chromium Authors. All rights reserved.
     Use of this source code is governed by a BSD-style license that can be
     found in the LICENSE file.
-->
# Contributing to Catapult

## Getting the code

Install [depot_tools]
(https://www.chromium.org/developers/how-tos/install-depot-tools)

`git clone https://github.com/catapult-project/catapult.git`

## Code style

We follow the [Chromium style](https://www.chromium.org/developers/coding-style).

## Code reviews

We use [Rietveld](https://codereview.chromium.org/) for code reviews. To upload
a CL to Rietveld, use `git cl upload` and be sure to add a project member as a
reviewer. When the CL has been LGTM-ed, you can land it with `git cl land`.

Note that in order to use `git cl`, it is necessary to have [depot_tools](
https://www.chromium.org/developers/how-tos/install-depot-tools) set up.

## Tests

Check individual project documentation for instructions on how to run tests.
You can also check the current status of our tests on the
[waterfall](http://build.chromium.org/p/client.catapult/waterfall).
Use the "commit" checkbox in rietveld to commit through the commit queue, which
automatically runs all tests. Run the tests before committing with the
"CQ dry run" link.
