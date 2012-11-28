#!/usr/bin/env python
#-*- coding: utf-8 -*-
#pylint: disable-msg=
"""
File       : test_qhash.py
Author     : Valentin Kuznetsov <vkuznet@gmail.com>
Description: Test qhash generated by das_hash, which is generated as
             32-bit number, whose upper 16-bits are complement
             of lower ones. Therefore we split string into two
             parts, convert it to int and apply AND operator. The
             result should be zero.
"""

# system modules
import os
import sys

def test(qhash):
    "test function"
    upper = int(qhash[:16], 16)
    lower = int(qhash[16:], 16)
    print "Input qhash", qhash
    print "lower qhash", qhash[16:], lower
    print "upper qhash", qhash[:16], upper
    return upper & lower == 0

def main(qhash):
    "Test qhash"
    if  test(qhash):
        print "OK"
    else:
        print "FAIL"

if __name__ == '__main__':
    if  len(sys.argv) != 2:
        print "Usage: test_qhash <hash>"
        sys.exit(1)
    main(sys.argv[1])