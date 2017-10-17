# ----------------------------------------------------------------------
#    Copyright (C) 2013 Kshitij Gupta <kgupta8592@gmail.com>
#    Copyright (C) 2017 Ruffin White <roxfoxpox@gmail.com>
#
#    This program is free software; you can redistribute it and/or
#    modify it under the terms of version 2 of the GNU General Public
#    License as published by the Free Software Foundation.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
# ----------------------------------------------------------------------
import os
import shutil
import subprocess
import unittest

from argparse import Namespace

import comarmor.tools
from common import CATest, read_file, setup_all_loops


PWD = os.path.dirname(os.path.realpath(__file__))
TEST_PROFILES_DIR = os.path.join(PWD, 'comarmor.d')

class MinitoolsTest(CATest):

    def CASetup(self):
        self.createTmpdir()

        #copy the local profiles to the test directory
        #Should be the set of cleanprofile
        self.profile_dir = os.path.join(self.tmpdir, 'profiles')
        shutil.copytree(TEST_PROFILES_DIR, self.profile_dir, symlinks=True)

    def test_cleanprof(self):
        raw_input_profile = 'cleanprof_test.in'
        exp_output_profile = 'cleanprof_test.out'
        raw_input_file = os.path.join(PWD,'data', raw_input_profile)
        exp_output_file = os.path.join(PWD,'data', exp_output_profile)
        #We position the local testfile
        shutil.copy(raw_input_file, self.profile_dir)
        real_output_file = os.path.join(self.profile_dir, raw_input_profile)

        #Our silly test program whose profile we wish to clean
        cleanprof_test = ['/a/simple/cleanprof/test/profile']

        args = Namespace(dir=self.profile_dir, program=cleanprof_test, silent=True)
        clean = comarmor.tools.ca_tools('cleanprof', args)

        clean.cleanprof_act()

        #Strip off the first line (#modified line)
        subprocess.check_output('sed -i 1d %s' % real_output_file, shell=True)

        exp_content = read_file(exp_output_file)
        real_content = read_file(real_output_file)
        self.maxDiff = None
        self.assertEqual(exp_content, real_content, 'Failed to cleanup profile properly')


setup_all_loops(__name__)
if __name__ == '__main__':
    unittest.main(verbosity=2)
