#!/bin/bash
# Create the skeleton for a polymer element.
# ./new-element time-stamp > elements/time-stamp.html

spinal=$1
camel=$(sed -r 's/(^|-)([a-z])/\U\2/g' <<< "${spinal}")

cat <<- _EOF_
<link rel="import" href="/bower_components/polymer/polymer.html">

<dom-module id="${spinal}">
  <template>
    <style>
    </style>
  </template>
  <script>
    'use strict';

    /**
     * \`<${spinal}>\` ....
     *
     *   Element description here.
     *
     * @customElement
     * @polymer
     * @demo /demo/${spinal}_demo.html
     */
    class ${camel} extends Polymer.Element {
      static get is() { return '${spinal}'; }

      static get properties() {
        return {
        }
      }

    }
    customElements.define(${camel}.is, ${camel});
  </script>
<dom-module>
_EOF_
