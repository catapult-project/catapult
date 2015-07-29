#!/bin/bash

mkdir -p build/
java -jar compiler.jar \
    --compilation_level ADVANCED_OPTIMIZATIONS \
    --generate_exports \
    --output_wrapper="(function(){%output%})();" \
    --warning_level VERBOSE \
    --js ./closure/base.js \
    --js ./closure/debug/error.js \
    --js ./closure/string/string.js \
    --js util.js \
    --js ./closure/json.js \
    --js ./closure/xmlhttpfactory.js \
    --js ./closure/wrapperxmlhttpfactory.js \
    --js ./closure/xmlhttp.js \
    --js messages.js \
    --js descriptor.js \
    --js protorpc.js \
    > build/protorpc_lib.js
