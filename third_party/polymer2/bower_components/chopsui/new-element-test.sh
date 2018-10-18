#!/bin/bash                                                                                     
# Create the skeleton for a polymer element.
# ./new-element-test time-stamp > test/time-stamp_test.html

spinal=$1
camel=$(sed -r 's/(^|-)([a-z])/\U\2/g' <<< "${spinal}")

cat <<- _EOF_
<!DOCTYPE html>
<title>${camel}</title>
<meta charset="utf-8">
<script src="/bower_components/webcomponentsjs/webcomponents-lite.js"></script>
<script src="/bower_components/web-component-tester/browser.js"></script>
<link rel="import" href="/elements/${spinal}.html">

<test-fixture id="${spinal}-test">
  <template>
    <${spinal}></${spinal}>
  </template>
</test-fixture>

<script>
  'use strict';

  suite('${spinal}', function() {
    let element;
    setup(function() {
      element = fixture('${spinal}-test');

    });

    test('TEST DESCRIPTION', function(done) {

      done();
    });

  });
</script>

_EOF_
