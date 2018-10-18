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

import fnmatch
import re

# from xml.etree import cElementTree as ElementTree
# import networkx as nx


colors = {
    'profile': '#38761dff',
    'topic': '#0b5394ff',
    'ros_topic': '#0b5394ff',
    'ros_service': '#741b47ff',
    'ros_action': '#351c75ff',
    'ros_permater': '#bf9000ff',
    'allow': 'green',
    'deny': 'red',
    'publish': '#3d85c6',
    'subscribe': '#3d85c6',
    'ros_publish': '#3d85c6',
    'ros_subscribe': '#3d85c6',
    'ros_call': '#a64d79',
    'ros_execute': '#a64d79',
}


def swap(x, y):
    return y, x


def keep(x, y):
    return x, y


directions = {
    'publish': keep,
    'subscribe': swap,
    'ros_publish': keep,
    'ros_subscribe': swap,
    'ros_call': keep,
    'ros_execute': swap,
}


def get_all_subjects_from_profile(profile):
    subjects = []
    profiles = profile.findall('.//profile')
    for name in profiles.findall('./profile/attachment'):
        subjects.append(name)
    return set(subjects)


def add_edges_from_profile(profile, G):
    for element in list(profile):
        if element.tag == 'profile':
            add_edges_from_profile(element, G)
        elif element.tag in ['attachment']:
            pass
        else:
            for subject_element in profile.findall('attachments/attachment'):
                subject_name = subject_element.text
                for object_element in element.findall('attachments/attachment'):
                    object_name = object_element.text
                    G.add_node(subject_name, type='subject', kind='subject',
                               color=colors[profile.tag], style='filled', fontcolor='white')
                    G.add_node(object_name, type='object', kind=element.tag,
                               color=colors[element.tag], style='filled', fontcolor='white')
                    for permission in list(element.find('permissions')):
                        u, v = directions[permission.tag](subject_name, object_name)
                        G.add_edge(u, v, label=permission.tag, color=colors[permission.tag])


def check_rule(rule, object_name, permission):
    for attachment in rule.findall('attachments/attachment'):
        patern = re.compile(fnmatch.translate(attachment.text))
        if patern.match(object_name):
            match = rule.find('permissions/' + permission)
            if match is not None:
                return rule
    else:
        return None


def check_rules(rules, object_name, permission):
    matchs = []
    for rule in rules:
        match = check_rule(rule, object_name, permission)
        if match:
            matchs.append(match)
    return matchs


def get_permissions(G, subject_name, object_name):
    permissions = []
    permissionA = G.get_edge_data(subject_name, object_name)
    permissionB = G.get_edge_data(object_name, subject_name)
    for permission in [permissionA, permissionB]:
        if permission:
            permissions.append(permission)
    return permissions


def check_edges_from_profile(profile, G):
    subjects = [(n, v) for n, v in G.nodes(data=True) if v['type'] == 'subject']
    for subject_name, subject_values in subjects:
        subject_profile = profile.filter_profile(subject_name).findall('./profile')
        object_names = G.to_undirected().neighbors(subject_name)
        for object_name in object_names:
            object_values = G.node[object_name]
            permissions = get_permissions(G, subject_name, object_name)
            for permission in permissions:
                permission_name = permission[0]['label']
                deny_rules = subject_profile.findall(
                    './/' + object_values['kind'] + '[@qualifier="DENY"]')
                deny_matchs = check_rules(deny_rules, object_name, permission_name)
                allow_rules = subject_profile.findall(
                    './/' + object_values['kind'] + '[@qualifier="ALLOW"]')
                allow_matchs = check_rules(allow_rules, object_name, permission_name)

                if deny_matchs:
                    qualifer = 'deny'
                elif allow_matchs:
                    qualifer = 'allow'
                else:
                    qualifer = 'deny'

                permission[0]['qualifer'] = qualifer
                permission[0]['color'] = colors[qualifer]
