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

from xml.etree import cElementTree as ElementTree


def compatible_permissions(rule, compressed_rule):
    permissions = rule.find('permissions')
    compressed_permissions = compressed_rule.find('permissions')
    if not permissions == compressed_permissions:
        if compressed_permissions is None:
            return False
        else:
            permissions = [i.tag for i in permissions.iter()]
            compressed_permissions = [i.tag for i in compressed_permissions.iter()]
            if not set(permissions) == set(compressed_permissions):
                return False
    return True


def compress_profile(profile):
    compressed_profile = ElementTree.Element('profile')
    compressed_profile.set('name', profile.get('name'))

    for rule in list(profile):
        compressed_rules = compressed_profile.findall(rule.tag)
        if compressed_rules is None:
            compressed_profile.append(rule)
        else:
            for compressed_rule in compressed_rules:
                if compatible_permissions(rule, compressed_rule):
                    attachments = rule.find('attachments')
                    compressed_attachments = compressed_rule.find('attachments')
                    compressed_attachments.extend(attachments)
                    break
            else:
                compressed_profile.append(rule)

    return compressed_profile


def compress_profiles(profiles):
    compressed_profiles = ElementTree.Element('profiles')
    for profile in list(profiles):
        compressed_profile = compress_profile(profile)
        compressed_profiles.append(compressed_profile)
    return compressed_profiles


def sort_by_text(parent):
    try:
        parent[:] = sorted(parent, key=lambda child: child.text)
    except:
        pass


def sort_by_tag(parent):
    try:
        parent[:] = sorted(parent, key=lambda child: child.tag)
    except:
        pass


def sort_by_name(parent):
    try:
        parent[:] = sorted(parent, key=lambda child: child.get('name'))
    except:
        pass


def sort_by_attachment(parent):
    try:
        parent[:] = sorted(parent, key=lambda child: (
            child.tag != 'attachments',
            child.findtext('attachments/attachment')))
    except:
        pass


def sort_profiles(profiles):
    for i in profiles.iter():
        sort_by_text(i)
    for i in profiles.iter():
        sort_by_tag(i)
    for i in profiles.iter():
        sort_by_name(i)
    for i in profiles.iter():
        sort_by_attachment(i)
