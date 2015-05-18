# Contributing to Catapult

## Getting the code

We recommend [setting up ssh keys](https://help.github.com/articles/generating-ssh-keys/)
and using the ssh url to clone (`git clone git@github.com:catapult-project/catapult.git`)
This alleviates the need to type your password when using Rietveld (see below).

## Code style

We follow the [Chromium style](https://www.chromium.org/developers/coding-style).

## Code reviews

We use [Rietveld](https://codereview.chromium.org/) for code reviews. To upload
a CL to Rietveld, use `git cl upload` and be sure to add a project member as a
reviewer. When the CL has been LGTM-ed, you can land it with `git cl land`.

Note that in order to use `git cl`, it is necessary to have [depot_tools](
https://www.chromium.org/developers/how-tos/install-depot-tools) set up.

## Tests

You can run tests locally with `./base/util/run_tests.py`. You can also check the
current status of our tests on the
[waterfall](http://build.chromium.org/p/client.catapult/waterfall).
