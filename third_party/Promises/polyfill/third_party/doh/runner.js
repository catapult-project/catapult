//guarantee in global scope and scope protection
(function(/* Array? */scriptArgs) {

//here's the definition of doh.runner...which really defines global doh
var d = function(doh) {
//
// Utility Functions and Classes
//

if (typeof this["print"] == "undefined" && console) {
  print = console.log.bind(console);
}

doh.global = this;

doh.squelch = true;
doh._print = print;

doh._line = "------------------------------------------------------------";

doh.debug = function(){
  // summary:
  //    takes any number of arguments and sends them to whatever debugging
  //    or logging facility is available in this environment

  var a = Array.prototype.slice.call(arguments, 0);
  a.unshift("|");
  doh._print(a.join(" "));
}

doh.error = function(){
  // summary:
  //    logging method to be used to send Error objects, so that
  //    whatever debugging or logging facility you have can decide to treat it
  //    as an Error object and show additional information - such as stack trace

  // YOUR TEST RUNNER NEEDS TO IMPLEMENT THIS
  var a = Array.prototype.slice.call(arguments, 0);
  a.unshift("ERROR:");
  doh._print(a.join(" "));
}

doh._AssertFailure = function(msg, hint){
  // idea for this as way of dis-ambiguating error types is from JUM.
  // The JUM is dead! Long live the JUM!

  if(!(this instanceof doh._AssertFailure)){
    return new doh._AssertFailure(msg, hint);
  }
  if(hint){
    msg = (new String(msg||""))+" with hint: \n\t\t"+(new String(hint)+"\n");
  }
  this.message = new String(msg||"");
  return this;
}
doh._AssertFailure.prototype = new Error();
doh._AssertFailure.prototype.constructor = doh._AssertFailure;
doh._AssertFailure.prototype.name = "doh._AssertFailure";

//
// State Keeping and Reporting
//

doh._testCount = 0;
doh._groupCount = 0;
doh._errorCount = 0;
doh._failureCount = 0;
doh._currentGroup = null;
doh._currentTest = null;

doh._init = function(){
  this._currentGroup = null;
  this._currentTest = null;
  this._errorCount = 0;
  this._failureCount = 0;
  this.debug(this._testCount, "tests to run in", this._groupCount, "groups");
}

// doh._urls = [];
doh._groups = {};

//
// Test Registration
//

doh.registerTestNs = function(/*String*/ group, /*Object*/ ns){
  // summary:
  //    adds the passed namespace object to the list of objects to be
  //    searched for test groups. Only "public" functions (not prefixed
  //    with "_") will be added as tests to be run. If you'd like to use
  //    fixtures (setUp(), tearDown(), and runTest()), please use
  //    registerTest() or registerTests().
  for(var x in ns){
    if( (x.charAt(0) != "_") &&
      (typeof ns[x] == "function") ){
      this.registerTest(group, ns[x]);
    }
  }
}

doh._testRegistered = function(group, fixture){
  // slot to be filled in
}

doh._groupStarted = function(group){
  // slot to be filled in
}

doh._groupFinished = function(group, success){
  // slot to be filled in
}

doh._testStarted = function(group, fixture){
  // slot to be filled in
}

doh._testFinished = function(group, fixture, success){
  // slot to be filled in
}

doh.registerGroup = function( /*String*/ group,
                /*Array||Function||Object*/ tests,
                /*Function*/ setUp,
                /*Function*/ tearDown,
                /*String*/ type){
  // summary:
  //    registers an entire group of tests at once and provides a setUp and
  //    tearDown facility for groups. If you call this method with only
  //    setUp and tearDown parameters, they will replace previously
  //    installed setUp or tearDown functions for the group with the new
  //    methods.
  // group:
  //    string name of the group
  // tests:
  //    either a function or an object or an array of functions/objects. If
  //    an object, it must contain at *least* a "runTest" method, and may
  //    also contain "setUp" and "tearDown" methods. These will be invoked
  //    on either side of the "runTest" method (respectively) when the test
  //    is run. If an array, it must contain objects matching the above
  //    description or test functions.
  // setUp: a function for initializing the test group
  // tearDown: a function for initializing the test group
  // type: The type of tests these are, such as a group of performance tests
  //    null/undefied are standard DOH tests, the valye 'perf' enables
  //    registering them as performance tests.
  if(tests){
    this.register(group, tests, type);
  }
  if(setUp){
    this._groups[group].setUp = setUp;
  }
  if(tearDown){
    this._groups[group].tearDown = tearDown;
  }
}

doh._getTestObj = function(group, test, type){
  var tObj = test;
  if(typeof test == "string"){
    if(test.substr(0, 4)=="url:"){
      return this.registerUrl(group, test);
    }else{
      tObj = {
        name: test.replace("/\s/g", "_") // FIXME: bad escapement
      };
      tObj.runTest = new Function("t", test);
    }
  }else if(typeof test == "function"){
    // if we didn't get a fixture, wrap the function
    tObj = { "runTest": test };
    if(test["name"]){
      tObj.name = test.name;
    }else{
      try{
        var fStr = "function ";
        var ts = tObj.runTest+"";
        if(0 <= ts.indexOf(fStr)){
          tObj.name = ts.split(fStr)[1].split("(", 1)[0];
        }
        // doh.debug(tObj.runTest.toSource());
      }catch(e){
      }
    }
    // FIXME: try harder to get the test name here
  }
  return tObj;
}

doh.registerTest = function(/*String*/ group,
                            /*Function||Object*/ test,
                            /*String*/ type){
  // summary:
  //    add the provided test function or fixture object to the specified
  //    test group.
  // group:
  //    string name of the group to add the test to
  // test:
  //    either a function or an object. If an object, it must contain at
  //    *least* a "runTest" method, and may also contain "setUp" and
  //    "tearDown" methods. These will be invoked on either side of the
  //    "runTest" method (respectively) when the test is run.
  // type:
  //    An identifier denoting the type of testing that the test performs, such
  //    as a performance test.  If null, defaults to regular DOH test.
  if(!this._groups[group]){
    this._groupCount++;
    this._groups[group] = [];
    this._groups[group].inFlight = 0;
  }
  var tObj = this._getTestObj(group, test, type);
  if(!tObj){ return null; }
  this._groups[group].push(tObj);
  this._testCount++;
  this._testRegistered(group, tObj);
  return tObj;
};

doh.registerTests = function(/*String*/ group,
                             /*Array*/ testArr,
                             /*String*/ type){
  // summary:
  //    registers a group of tests, treating each element of testArr as
  //    though it were being (along with group) passed to the registerTest
  //    method.  It also uses the type to decide how the tests should
  //    behave, by defining the type of tests these are, such as performance
  //    tests
  var register = this.registerTest.bind(this, group);
  testArr.forEach(function(test) { register(test, type); });
};

// FIXME: remove the doh.add alias SRTL.
doh.register = doh.add = function(groupOrNs, testOrNull, type){
  // summary:
  //    "magical" variant of registerTests, registerTest, and
  //    registerTestNs. Will accept the calling arguments of any of these
  //    methods and will correctly guess the right one to register with.
  if( (arguments.length == 1)&&
    (typeof groupOrNs == "string") ){
    if(groupOrNs.substr(0, 4)=="url:"){
      this.registerUrl(groupOrNs, null, null, type);
    }else{
      this.registerTest("ungrouped", groupOrNs, type);
    }
  }
  if(arguments.length == 1){
    this.debug("invalid args passed to doh.register():", groupOrNs, ",", testOrNull);
    return;
  }
  if(typeof testOrNull == "string"){
    if(testOrNull.substr(0, 4)=="url:"){
      this.registerUrl(testOrNull, null, null, type);
    }else{
      this.registerTest(groupOrNs, testOrNull, type);
    }
    // this.registerTestNs(groupOrNs, testOrNull);
    return;
  }
  if(doh._isArray(testOrNull)){
    this.registerTests(groupOrNs, testOrNull, type);
    return;
  }
  this.registerTest(groupOrNs, testOrNull, type);
};

//
// Assertions and In-Test Utilities
//

doh.t = doh.assertTrue = function(/*Object*/ condition, /*String?*/ hint){
  // summary:
  //    is the passed item "truthy"?
  if(arguments.length < 1){
    throw new doh._AssertFailure(
      "assertTrue failed because it was not passed at least 1 argument"
    );
  }
  if(!eval(condition)){
    throw new doh._AssertFailure("assertTrue('" + condition + "') failed", hint);
  }
}

doh.f = doh.assertFalse = function(/*Object*/ condition, /*String?*/ hint){
  // summary:
  //    is the passed item "falsey"?
  if(arguments.length < 1){
    throw new doh._AssertFailure(
      "assertFalse failed because it was not passed at least 1 argument"
    );
  }

  if(eval(condition)){
    throw new doh._AssertFailure("assertFalse('" + condition + "') failed", hint);
  }
}

doh.e = doh.assertError = function(/*Error object*/expectedError,
                                   /*Object*/scope,
                                   /*String*/functionName,
                                   /*Array*/args,
                                   /*String?*/ hint){
  //  summary:
  //    Test for a certain error to be thrown by the given function.
  //  example:
  //    t.assertError(dojox.data.QueryReadStore.InvalidAttributeError, store, "getValue", [item, "NOT THERE"]);
  //    t.assertError(dojox.data.QueryReadStore.InvalidItemError, store, "getValue", ["not an item", "NOT THERE"]);
  try{
    scope[functionName].apply(scope, args);
  }catch (e){
    if(e instanceof expectedError){
      return true;
    }else{
      throw new doh._AssertFailure(
        "assertError() failed:\n\texpected error\n\t\t" +
          expectedError + "\n\tbut got\n\t\t" + e +"\n\n",
        hint
      );
    }
  }
  throw new doh._AssertFailure(
    "assertError() failed:\n\texpected error\n\t\t" +
      expectedError+"\n\tbut no error caught\n\n",
    hint
  );
}


doh.is = doh.assertEqual = function(/*Object*/ expected, /*Object*/ actual, /*String?*/ hint){
  // summary:
  //    are the passed expected and actual objects/values deeply
  //    equivalent?

  // Compare undefined always with three equal signs, because undefined==null
  // is true, but undefined===null is false.
  if((expected === undefined)&&(actual === undefined)){
    return true;
  }
  if(arguments.length < 2){
    throw doh._AssertFailure(
        "assertEqual failed because it was not passed 2 arguments");
  }
  if(
    (expected === actual) ||
    (expected == actual) ||
    ( typeof expected == "number" &&
      typeof actual == "number" &&
      isNaN(expected) && isNaN(actual)
    )
  ){
    return true;
  }
  if(
    (this._isArray(expected) &&
     this._isArray(actual)
    ) &&
    this._arrayEq(expected, actual)
  ){
    return true;
  }
  if(
    (typeof expected == "object" && typeof actual == "object") &&
    this._objPropEq(expected, actual)
  ){
    return true;
  }
  throw new doh._AssertFailure(
    "assertEqual() failed:\n\texpected\n\t\t"+expected+
        "\n\tbut got\n\t\t"+actual+"\n\n",
    hint);
}

doh.isNot = doh.assertNotEqual = function(/*Object*/ notExpected,
                                          /*Object*/ actual,
                                          /*String?*/ hint){
  // summary:
  //    are the passed notexpected and actual objects/values deeply
  //    not equivalent?

  // Compare undefined always with three equal signs, because undefined==null
  // is true, but undefined===null is false.
  if(
    (notExpected === undefined) &&
    (actual === undefined)
  ){
    throw new doh._AssertFailure(
      "assertNotEqual() failed: not expected |"+notExpected+
          "| but got |"+actual+"|",
      hint);
  }

  if(arguments.length < 2){
    throw doh._AssertFailure(
      "assertEqual failed because it was not passed 2 arguments"
    );
  }

  if((notExpected === actual)||(notExpected == actual)){
    throw new doh._AssertFailure(
      "assertNotEqual() failed: not expected |"+notExpected+
          "| but got |"+actual+"|",
      hint);
  }

  if( (this._isArray(notExpected) && this._isArray(actual))&&
    (this._arrayEq(notExpected, actual)) ){
    throw new doh._AssertFailure(
      "assertNotEqual() failed: not expected |"+notExpected+
          "| but got |"+actual+"|",
      hint);
  }
  if( ((typeof notExpected == "object")&&((typeof actual == "object"))) ){
    var isequal = false;
    try{
      isequal = this._objPropEq(notExpected, actual);
    } catch(e) {
      if( !(e instanceof doh._AssertFailure) ){
        throw e; //other exceptions, just throw it
      }
    }
    if (isequal) {
      throw new doh._AssertFailure(
        "assertNotEqual() failed: not expected |"+notExpected+
            "| but got |"+actual+"|",
        hint);
    }
  }
    return true;
}

doh._arrayEq = function(expected, actual){
  if (expected.length != actual.length) {
    return false;
  }

  for(var x=0; x<expected.length; x++){
    if (!doh.assertEqual(expected[x], actual[x])) { return false; }
  }
  return true;
}

doh._objPropEq = function(expected, actual){
  // Degenerate case: if they are both null, then their "properties" are equal.
  if (expected === null && actual === null) {
    return true;
  }

  // If only one is null, they aren't equal.
  if (expected === null || actual === null) {
    return false;
  }

  if (expected instanceof Date) {
    return actual instanceof Date && expected.getTime() == actual.getTime();
  }

  var x;
  // Make sure ALL THE SAME properties are in both objects!
  for (x in actual) { // Lets check "actual" here, expected is checked below.
    if (expected[x] === undefined) {
      return false;
    }
  };

  for (x in expected) {
    if (!doh.assertEqual(expected[x], actual[x])) {
      return false;
    }
  }

  return true;
}

doh._isArray = function(it){
  return (it && it instanceof Array || typeof it == "array");
}

//
// Runner-Wrapper
//
doh._setupGroupForRun = function(/*String*/ groupName, /*Integer*/ idx){
  var tg = this._groups[groupName];
  this.debug(this._line);
  this.debug("GROUP", "\""+groupName+"\"", "has", tg.length, "test"+((tg.length > 1) ? "s" : "")+" to run");
}

doh._handleFailure = function(groupName, fixture, e){
  // this.debug("FAILED test:", fixture.name);
  // mostly borrowed from JUM
  this._groups[groupName].failures++;
  var out = "";
  if(e instanceof this._AssertFailure){
    this._failureCount++;
    if(e["fileName"]){ out += e.fileName + ':'; }
    if(e["lineNumber"]){ out += e.lineNumber + ' '; }
    out += e+": "+e.message;
    this.debug("\t_AssertFailure:", out);
  }else{
    this._errorCount++;
  }
  this.error(e);
  if(fixture.runTest["toSource"]){
    var ss = fixture.runTest.toSource();
    this.debug("\tERROR IN:\n\t\t", ss);
  }else{
    this.debug("\tERROR IN:\n\t\t", fixture.runTest);
  }
  if (e.rhinoException) {
    e.rhinoException.printStackTrace();
  } else if(e.javaException) {
    e.javaException.printStackTrace();
  }

  if (!doh.squelch) {
    throw e;
  }

}

doh._runFixture = function(groupName, fixture){
  var tg = this._groups[groupName];
  this._testStarted(groupName, fixture);
  var err = null;
  // run it, catching exceptions and reporting them
  try{
    doh.debug(fixture.name);
    // let doh reference "this.group.thinger..." which can be set by
    // another test or group-level setUp function
    fixture.group = tg;
    // only execute the parts of the fixture we've got

    if(fixture["setUp"]){
      fixture.setUp(this);
    }
    if(fixture["runTest"]){  // should we error out of a fixture doesn't have a runTest?
      fixture.startTime = new Date();
      var ret = fixture.runTest(this);
      fixture.endTime = new Date();
      if(ret){
        return ret;
      }
    }
    if(fixture["tearDown"]){
      fixture.tearDown(this);
    }
  }catch(e){
    this._handleFailure(groupName, fixture, e);
    err = e;
    if(!fixture.endTime){
      fixture.endTime = new Date();
    }
  }
}

doh._testId = 0;
doh.runGroup = function(/*String*/ groupName, /*Integer*/ idx){
  // summary:
  //    runs the specified test group

  var tg = this._groups[groupName];
  if(tg.skip === true){ return; }
  if(this._isArray(tg)){
    if(idx<=tg.length){
      if(!tg.inFlight){
        if(tg["tearDown"]){ tg.tearDown(this); }
        doh._groupFinished(groupName, !tg.failures);
        return;
      }
    }
    if(!idx){
      tg.inFlight = 0;
      tg.iterated = false;
      tg.failures = 0;
    }
    doh._groupStarted(groupName);
    if(!idx){
      this._setupGroupForRun(groupName, idx);
      if(tg["setUp"]){ tg.setUp(this); }
    }
    for(var y=(idx||0); y<tg.length; y++){
      doh._runFixture(groupName, tg[y]);
    }
    tg.iterated = true;
    if(!tg.inFlight){
      if(tg["tearDown"]){ tg.tearDown(this); }
      doh._groupFinished(groupName, !tg.failures);
    }
  }
}

doh._onEnd = function(){}

doh._report = function(){
  // summary:
  //    a private method to be implemented/replaced by the "locally
  //    appropriate" test runner

  this.debug(this._line);
  this.debug("| TEST SUMMARY:");
  this.debug(this._line);
  this.debug("\t", this._testCount, "tests in", this._groupCount, "groups");
  this.debug("\t", this._errorCount, "errors");
  this.debug("\t", this._failureCount, "failures");
}

doh.run = function(){
  // summary:
  //    begins or resumes the test process.
  // this.debug("STARTING");
  var cg = this._currentGroup;
  var ct = this._currentTest;
  var found = false;
  if(!cg){
    this._init();
    found = true;
  }
  this._currentGroup = null;
  this._currentTest = null;

  for(var x in this._groups){
    if( (
          (!found) && (x == cg)
        )||
        ( found )
      ){
      this._currentGroup = x;
      if(!found){
        found = true;
        this.runGroup(x, ct);
      }else{
        this.runGroup(x);
      }
    }
  }
  this._currentGroup = null;
  this._currentTest = null;
  this._onEnd();
  this._report();
};
return doh;
}; //end of definition of doh/runner, which really defines global doh

// this is guaranteed in the global scope, not matter what kind of eval is
// thrown at us define global doh
if(typeof doh == "undefined") {
  doh = {};
}
if(typeof define == "undefined" || define.vendor=="dojotoolkit.org") {
  // using dojo 1.x loader or no dojo on the page
  d(doh);
}else{
  // using an AMD loader
  doh.runnerFactory = d;
}

}).call(null, typeof arguments=="undefined" ?
                  [] : Array.prototype.slice.call(arguments)
        );
