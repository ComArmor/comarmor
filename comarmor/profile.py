# Copyright 2018 Open Source Robotics Foundation, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
from collections.abc import MutableSequence

from .exceptions import InvalidProfile


class Profile:
    """Object representation of comarmor profile"""

    __slots__ = [
        'tree',
    ]

    def __init__(self, **kwargs):

        # initialize all slots with values
        for attr in self.__slots__:
            value = kwargs[attr] if attr in kwargs else None
            setattr(self, attr, value)

        # verify that no unknown keywords are passed
        unknown = set(kwargs.keys()).difference(self.__slots__)
        if unknown:
            raise TypeError('Unknown properties: %s' % ', '.join(unknown))

    def __str__(self):
        data = {}
        for attr in self.__slots__:
            data[attr] = getattr(self, attr)
        return str(data)


class ProfileStorage(MutableSequence):
    """Object representation of comarmor profiles"""

    __slots__ = [
        'profiles',
    ]

    def __init__(self, **kwargs):

        # initialize all slots with values
        for attr in self.__slots__:
            value = kwargs[attr] if attr in kwargs else []
            setattr(self, attr, value)

        # verify that no unknown keywords are passed
        unknown = set(kwargs.keys()).difference(self.__slots__)
        if unknown:
            raise TypeError('Unknown properties: %s' % ', '.join(unknown))


        super().__init__()

    def __getitem__(self, key):
        return self.profiles.__getitem__(key)

    def __len__(self):
        return self.profiles.__len__()

    def __delitem__(self, key):
        self.profiles.__delitem__(key)

    def __setitem__(self, key, value):
        self.profiles.__setitem__(key, value)

    def insert(self, key, value):
        self.profiles.insert(key,value)

    def __str__(self):
        data = {}
        for attr in self.__slots__:
            data[attr] = getattr(self, attr)
        return str(data)
