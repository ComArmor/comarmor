# Copyright 2012 Canonical Ltd.
# Copyright 2013 Kshitij Gupta <kgupta8592@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of version 2 of the GNU General Public
# License published by the Free Software Foundation.


import re


def convert_regexp(regexp):
    regex_paren = re.compile('^(.*){([^}]*)}(.*)$')
    regexp = regexp.strip()
    new_reg = re.sub(r'(?<!\\)(\.|\+|\$)', r'\\\1', regexp)

    while regex_paren.search(new_reg):
        match = regex_paren.search(new_reg).groups()
        prev = match[0]
        after = match[2]
        p1 = match[1].replace(',', '|')
        new_reg = prev + '(' + p1 + ')' + after

    new_reg = new_reg.replace('?', '[^/\000]')

    multi_glob = '__KJHDKVZH_AAPROF_INTERNAL_GLOB_SVCUZDGZID__'
    new_reg = new_reg.replace('**', multi_glob)

    # Match atleast one character if * or ** after /
    # ?< is the negative lookback operator
    new_reg = new_reg.replace('*', '(((?<=/)[^/\000]+)|((?<!/)[^/\000]*))')
    new_reg = new_reg.replace(multi_glob, '(((?<=/)[^\000]+)|((?<!/)[^\000]*))')
    if regexp[0] != '^':
        new_reg = '^' + new_reg
    if regexp[-1] != '$':
        new_reg = new_reg + '$'
    return new_reg
