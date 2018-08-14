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

from collections.abc import MutableSequence
import copy
import re
from xml.etree import cElementTree as ElementTree

from .xml.regex import convert_regexp


def filter_rec(node, element, func):
    """Filter recursively all attachable comarmor profile."""
    for item in node.findall(element):
        if func(item):
            node.remove(item)
        else:
            filter_rec(item, element, func)


class Profile:
    """Object representation of comarmor profile."""

    __slots__ = [
        'path',
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

    def empty(self):
        return self.tree.find('profile') is None

    def filter_profile(self, key):
        filtered_profile = copy.deepcopy(self)
        root = filtered_profile.tree.getroot()

        def filter_func(node):
            attachment = node.find('attachment').text
            patern = re.compile(convert_regexp(attachment))
            return not patern.match(key)

        filter_rec(node=root, element='profile', func=filter_func)

        return filtered_profile

    def extract_rules(self, kind):
        root = self.tree.getroot()
        rules = ElementTree.Element('rules')
        rules.extend(root.findall('.//{}'.format(kind)))
        return rules

    def findall(self, path, namespaces=None):
        root = self.tree.getroot()
        results = ElementTree.Element('results')
        results.extend(root.findall(path, namespaces))
        return results


class ProfileStorage(MutableSequence):
    """Object representation of comarmor profiles."""

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
        self.profiles.insert(key, value)

    def __str__(self):
        data = {}
        for attr in self.__slots__:
            data[attr] = getattr(self, attr)
        return str(data)

    def filter_profile(self, key):
        profile_storage = copy.deepcopy(self)
        for i in reversed(range(len(profile_storage))):
            profile_storage[i] = profile_storage[i].filter_profile(key)
            if profile_storage[i].empty():
                del profile_storage[i]
        return profile_storage

    def extract_rules(self, kind):
        rules = ElementTree.Element('rules')
        for profile in self:
            rules.extend(profile.extract_rules(kind))
        return rules

    def findall(self, path, namespaces=None):
        results = ElementTree.Element('results')
        for profile in self:
            results.extend(profile.findall(path, namespaces))
        return results
