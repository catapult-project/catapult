"use strict";

var sinon = require("sinon");
var AssertionError = require("chai").AssertionError;
var expect = require("chai").expect;

describe("Call count", function () {
    var spy = null;

    beforeEach(function () {
        spy = sinon.spy();
    });

    describe("called", function () {
        it("should throw an assertion error when the spy is undefined", function () {
            expect(function () {
                expect(undefined).to.have.been.called;
            }).to.throw(TypeError);
        });

        it("should throw an assertion error when the spy is not called", function () {
            expect(function () {
                spy.should.have.been.called;
            }).to.throw(AssertionError);
        });

        it("should not throw when the spy is called once", function () {
            spy();

            expect(function () {
                spy.should.have.been.called;
            }).to.not.throw();
        });

        it("should not throw when the spy is called twice", function () {
            spy();
            spy();

            expect(function () {
                spy.should.have.been.called;
            }).to.not.throw();
        });
    });

    describe("not called", function () {
        it("should not throw when the spy is not called", function () {
            expect(function () {
                spy.should.not.have.been.called;
            }).to.not.throw();
        });

        it("should throw an assertion error when the spy is called once", function () {
            spy();

            expect(function () {
                spy.should.not.have.been.called;
            }).to.throw(AssertionError);
        });
    });

    describe("callCount", function () {
        it("should throw an assertion error when the spy is not called", function () {
            expect(function () {
                spy.should.have.callCount();
            }).to.throw(AssertionError);
        });

        it("should not throw an assertion error when the number of calls equals provided call count", function () {
            spy();
            spy();
            spy();
            spy();

            expect(function () {
                spy.should.have.callCount(4);
            }).to.not.throw(AssertionError);
        });

        it("should throw an assertion error whenever the number of calls are not equal to provided call count",
        function () {
            spy();
            spy();
            spy();

            expect(function () {
                spy.should.have.callCount(4);
            }).to.throw(AssertionError);
        });
    });

    describe("calledOnce", function () {
        it("should throw an assertion error when the spy is not called", function () {
            expect(function () {
                spy.should.have.been.calledOnce;
            }).to.throw(AssertionError);
        });

        it("should not throw when the spy is called once", function () {
            spy();

            expect(function () {
                spy.should.have.been.calledOnce;
            }).to.not.throw();
        });

        it("should throw an assertion error when the spy is called twice", function () {
            spy();
            spy();

            expect(function () {
                spy.should.have.been.calledOnce;
            }).to.throw(AssertionError);
        });
    });

    describe("calledTwice", function () {
        it("should throw an assertion error when the spy is not called", function () {
            expect(function () {
                spy.should.have.been.calledTwice;
            }).to.throw(AssertionError);
        });

        it("should throw an assertion error when the spy is called once", function () {
            spy();

            expect(function () {
                spy.should.have.been.calledTwice;
            }).to.throw(AssertionError);
        });

        it("should not throw when the spy is called twice", function () {
            spy();
            spy();

            expect(function () {
                spy.should.have.been.calledTwice;
            }).to.not.throw();
        });

        it("should throw an assertion error when the spy is called thrice", function () {
            spy();
            spy();
            spy();

            expect(function () {
                spy.should.have.been.calledTwice;
            }).to.throw(AssertionError);
        });
    });

    describe("calledThrice", function () {
        it("should throw an assertion error when the spy is not called", function () {
            expect(function () {
                spy.should.have.been.calledThrice;
            }).to.throw(AssertionError);
        });

        it("should throw an assertion error when the spy is called once", function () {
            spy();

            expect(function () {
                spy.should.have.been.calledThrice;
            }).to.throw(AssertionError);
        });

        it("should throw an assertion error when the spy is called twice", function () {
            spy();
            spy();

            expect(function () {
                spy.should.have.been.calledThrice;
            }).to.throw(AssertionError);
        });

        it("should not throw when the spy is called thrice", function () {
            spy();
            spy();
            spy();

            expect(function () {
                spy.should.have.been.calledThrice;
            }).to.not.throw();
        });

        it("should throw an assertion error when the spy is called four times", function () {
            spy();
            spy();
            spy();
            spy();

            expect(function () {
                spy.should.have.been.calledThrice;
            }).to.throw(AssertionError);
        });
    });
});
