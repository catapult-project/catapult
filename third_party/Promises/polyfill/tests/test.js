// In which Node proves to, perhaps, be good for soemthing after all
var filemap = require("filemap");
var _eval = require("eval");

var files = [
  "../third_party/doh/runner_async.js",
  "../src/Promise.js",
  "Promise-tests.js"
];

// ...jsut as soon as we re-build the naive load() method
filemap(
  files,
  "utf-8",
  function(contents) {
    var buff = "this.runningUnderTest = true;\n\n";
    files.forEach(function(n) {
      buff += contents[n];
    });
    buff += "doh.run();";
    _eval(buff);
  }
);
