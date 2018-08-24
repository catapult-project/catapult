"use strict";

var sinon = require("sinon");
var AssertionError = require("chai").AssertionError;
var expect = require("chai").expect;

describe("Call arguments", function () {
    var spy = null;
    var arg1 = null;
    var arg2 = null;
    var arg3 = null;
    var arg4 = null;
    var notArg = null;
    var any = null;

    beforeEach(function () {
        spy = sinon.spy();
        arg1 = "A";
        arg2 = "B";
        arg3 = { D: "E" };
        arg4 = { D: { E: { E: "P" } } };
        notArg = "C";
        any = sinon.match.any;
    });

    describe("calledWith", function () {
        it("should throw an assertion error when the spy is not called", function () {
            expect(function () {
                spy.should.have.been.calledWith(arg1, arg2);
            }).to.throw(AssertionError);
        });

        it("should not throw when the spy is called with the correct arguments", function () {
            spy(arg1, arg2);

            expect(function () {
                spy.should.have.been.calledWith(arg1, arg2);
            }).to.not.throw();
            expect(function () {
                spy.getCall(0).should.have.been.calledWith(arg1, arg2);
            }).to.not.throw();
        });

        it("should not throw when the spy is called with the correct arguments and more", function () {
            spy(arg1, arg2, notArg);

            expect(function () {
                spy.should.have.been.calledWith(arg1, arg2);
            }).to.not.throw();
            expect(function () {
                spy.getCall(0).should.have.been.calledWith(arg1, arg2);
            }).to.not.throw();
        });

        it("should throw an assertion error when the spy is called with incorrect arguments", function () {
            spy(notArg, arg1);

            expect(function () {
                spy.should.have.been.calledWith(arg1, arg2);
            }).to.throw(AssertionError);
            expect(function () {
                spy.getCall(0).should.have.been.calledWith(arg1, arg2);
            }).to.throw(AssertionError);
        });

        it("should not throw when the spy is called with incorrect arguments but then correct ones", function () {
            spy(notArg, arg1);
            spy(arg1, arg2);

            expect(function () {
                spy.should.have.been.calledWith(arg1, arg2);
            }).to.not.throw();
            expect(function () {
                spy.getCall(1).should.have.been.calledWith(arg1, arg2);
            }).to.not.throw();
        });

        it("should handle objects in arguments", function () {
            spy(arg1, arg3);
            var _arg3 = JSON.parse(JSON.stringify(arg3));

            expect(function () {
                spy.should.have.been.calledWith(arg1, _arg3);
            }).to.not.throw();
            expect(function () {
                spy.getCall(0).should.have.been.calledWith(arg1, _arg3);
            }).to.not.throw();
        });

        it("should handle deep objects in arguments", function () {
            spy(arg1, arg4);
            var _arg4 = JSON.parse(JSON.stringify(arg4));

            expect(function () {
                spy.should.have.been.calledWith(arg1, _arg4);
            }).to.not.throw();
            expect(function () {
                spy.getCall(0).should.have.been.calledWith(arg1, _arg4);
            }).to.not.throw();
        });
    });


    describe("always calledWith", function () {
        it("should throw an assertion error when the spy is not called", function () {
            expect(function () {
                spy.should.always.have.been.calledWith(arg1, arg2);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.always.been.calledWith(arg1, arg2);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.been.always.calledWith(arg1, arg2);
            }).to.throw(AssertionError);
        });

        it("should not throw when the spy is called with the correct arguments", function () {
            spy(arg1, arg2);

            expect(function () {
                spy.should.always.have.been.calledWith(arg1, arg2);
            }).to.not.throw();
            expect(function () {
                spy.should.have.always.been.calledWith(arg1, arg2);
            }).to.not.throw();
            expect(function () {
                spy.should.have.been.always.calledWith(arg1, arg2);
            }).to.not.throw();
        });

        it("should not throw when the spy is called with the correct arguments and more", function () {
            spy(arg1, arg2, notArg);

            expect(function () {
                spy.should.always.have.been.calledWith(arg1, arg2);
            }).to.not.throw();
            expect(function () {
                spy.should.have.always.been.calledWith(arg1, arg2);
            }).to.not.throw();
            expect(function () {
                spy.should.have.been.always.calledWith(arg1, arg2);
            }).to.not.throw();
        });

        it("should throw an assertion error when the spy is called with incorrect arguments", function () {
            spy(notArg, arg1);

            expect(function () {
                spy.should.always.have.been.calledWith(arg1, arg2);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.always.been.calledWith(arg1, arg2);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.been.always.calledWith(arg1, arg2);
            }).to.throw(AssertionError);
        });

        it("should throw an assertion error when the spy is called with incorrect arguments but then correct ones",
        function () {
            spy(notArg, arg1);
            spy(arg1, arg2);

            expect(function () {
                spy.should.always.have.been.calledWith(arg1, arg2);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.always.been.calledWith(arg1, arg2);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.been.always.calledWith(arg1, arg2);
            }).to.throw(AssertionError);
        });
    });

    describe("calledWithExactly", function () {
        it("should throw an assertion error when the spy is not called", function () {
            expect(function () {
                spy.should.have.been.calledWithExactly(arg1, arg2);
            }).to.throw(AssertionError);
        });

        it("should not throw when the spy is called with the correct arguments", function () {
            spy(arg1, arg2);

            expect(function () {
                spy.should.have.been.calledWithExactly(arg1, arg2);
            }).to.not.throw();
            expect(function () {
                spy.getCall(0).should.have.been.calledWithExactly(arg1, arg2);
            }).to.not.throw();
        });

        it("should throw an assertion error when the spy is called with the correct arguments and more", function () {
            spy(arg1, arg2, notArg);

            expect(function () {
                spy.should.have.been.calledWithExactly(arg1, arg2);
            }).to.throw(AssertionError);
            expect(function () {
                spy.getCall(0).should.have.been.calledWithExactly(arg1, arg2);
            }).to.throw(AssertionError);
        });

        it("should throw an assertion error when the spy is called with incorrect arguments", function () {
            spy(notArg, arg1);

            expect(function () {
                spy.should.have.been.calledWithExactly(arg1, arg2);
            }).to.throw(AssertionError);
            expect(function () {
                spy.getCall(0).should.have.been.calledWithExactly(arg1, arg2);
            }).to.throw(AssertionError);
        });

        it("should not throw when the spy is called with incorrect arguments but then correct ones", function () {
            spy(notArg, arg1);
            spy(arg1, arg2);

            expect(function () {
                spy.should.have.been.calledWithExactly(arg1, arg2);
            }).to.not.throw();
            expect(function () {
                spy.getCall(1).should.have.been.calledWithExactly(arg1, arg2);
            }).to.not.throw();
        });
    });


    describe("always calledWithExactly", function () {
        it("should throw an assertion error when the spy is not called", function () {
            expect(function () {
                spy.should.always.have.been.calledWithExactly(arg1, arg2);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.always.been.calledWithExactly(arg1, arg2);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.been.always.calledWithExactly(arg1, arg2);
            }).to.throw(AssertionError);
        });

        it("should not throw when the spy is called with the correct arguments", function () {
            spy(arg1, arg2);

            expect(function () {
                spy.should.always.have.been.calledWithExactly(arg1, arg2);
            }).to.not.throw();
            expect(function () {
                spy.should.have.always.been.calledWithExactly(arg1, arg2);
            }).to.not.throw();
            expect(function () {
                spy.should.have.been.always.calledWithExactly(arg1, arg2);
            }).to.not.throw();
        });

        it("should throw an assertion error when the spy is called with the correct arguments and more", function () {
            spy(arg1, arg2, notArg);

            expect(function () {
                spy.should.always.have.been.calledWithExactly(arg1, arg2);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.always.been.calledWithExactly(arg1, arg2);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.been.always.calledWithExactly(arg1, arg2);
            }).to.throw(AssertionError);
        });

        it("should throw an assertion error when the spy is called with incorrect arguments", function () {
            spy(notArg, arg1);

            expect(function () {
                spy.should.always.have.been.calledWithExactly(arg1, arg2);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.always.been.calledWithExactly(arg1, arg2);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.been.always.calledWithExactly(arg1, arg2);
            }).to.throw(AssertionError);
        });

        it("should throw an assertion error when the spy is called with incorrect arguments but then correct ones",
        function () {
            spy(notArg, arg1);
            spy(arg1, arg2);

            expect(function () {
                spy.should.always.have.been.calledWithExactly(arg1, arg2);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.always.been.calledWithExactly(arg1, arg2);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.been.always.calledWithExactly(arg1, arg2);
            }).to.throw(AssertionError);
        });
    });

    describe("calledWithMatch", function () {
        it("should throw an assertion error when the spy is not called", function () {
            expect(function () {
                spy.should.have.been.calledWithMatch(any, any);
            }).to.throw(AssertionError);
        });

        it("should not throw when the spy is called with the correct arguments", function () {
            spy(arg1, arg2);

            expect(function () {
                spy.should.have.been.calledWithMatch(any, any);
            }).to.not.throw();
            expect(function () {
                spy.getCall(0).should.have.been.calledWithMatch(any, any);
            }).to.not.throw();
        });

        it("should not throw when the spy is called with the correct arguments and more", function () {
            spy(arg1, arg2, notArg);

            expect(function () {
                spy.should.have.been.calledWithMatch(any, any);
            }).to.not.throw();
            expect(function () {
                spy.getCall(0).should.have.been.calledWithMatch(any, any);
            }).to.not.throw();
        });

        it("should throw an assertion error when the spy is called with incorrect arguments", function () {
            spy(notArg, arg1);

            expect(function () {
                spy.should.have.been.calledWithMatch(any, arg2);
            }).to.throw(AssertionError);
            expect(function () {
                spy.getCall(0).should.have.been.calledWithMatch(arg1, any);
            }).to.throw(AssertionError);
        });

        it("should not throw when the spy is called with incorrect arguments but then correct ones", function () {
            spy(notArg, arg1);
            spy(arg1, arg2);

            expect(function () {
                spy.should.have.been.calledWithMatch(arg1, arg2);
            }).to.not.throw();
            expect(function () {
                spy.getCall(1).should.have.been.calledWithMatch(arg1, arg2);
            }).to.not.throw();
        });
    });


    describe("always calledWithMatch", function () {
        it("should throw an assertion error when the spy is not called", function () {
            expect(function () {
                spy.should.always.have.been.calledWithMatch(any, any);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.always.been.calledWithMatch(arg1, any);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.been.always.calledWithMatch(any, arg2);
            }).to.throw(AssertionError);
        });

        it("should not throw when the spy is called with the correct arguments", function () {
            spy(arg1, arg2);

            expect(function () {
                spy.should.always.have.been.calledWithMatch(any, any);
            }).to.not.throw();
            expect(function () {
                spy.should.have.always.been.calledWithMatch(any, arg2);
            }).to.not.throw();
            expect(function () {
                spy.should.have.been.always.calledWithMatch(arg1, any);
            }).to.not.throw();
        });

        it("should not throw when the spy is called with the correct arguments and more", function () {
            spy(arg1, arg2, notArg);

            expect(function () {
                spy.should.always.have.been.calledWithMatch(any, any);
            }).to.not.throw();
            expect(function () {
                spy.should.have.always.been.calledWithMatch(any, arg2);
            }).to.not.throw();
            expect(function () {
                spy.should.have.been.always.calledWithMatch(arg1, any);
            }).to.not.throw();
        });

        it("should throw an assertion error when the spy is called with incorrect arguments", function () {
            spy(notArg, arg1);

            expect(function () {
                spy.should.always.have.been.calledWithMatch(any, arg2);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.always.been.calledWithMatch(arg1, any);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.been.always.calledWithMatch(arg1, arg2);
            }).to.throw(AssertionError);
        });

        it("should throw an assertion error when the spy is called with incorrect arguments but then correct ones",
        function () {
            spy(notArg, arg1);
            spy(arg1, arg2);

            expect(function () {
                spy.should.always.have.been.calledWithMatch(arg1, arg2);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.always.been.calledWithMatch(arg1, arg2);
            }).to.throw(AssertionError);
            expect(function () {
                spy.should.have.been.always.calledWithMatch(arg1, arg2);
            }).to.throw(AssertionError);
        });
    });
});
