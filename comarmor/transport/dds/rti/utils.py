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

from collections import defaultdict
from xml.etree import ElementTree


def nested_dict():
    return defaultdict(nested_dict)


def rchop(thestring, ending):
    if thestring.endswith(ending):
        return thestring[:-len(ending)]
    return thestring


def ros_topic(namespace):
    return namespace


def ros_request(namespace):
    return rchop(namespace, 'Request')


def ros_reply(namespace):
    return rchop(namespace, 'Reply')


object_naming = {
    'rt': ros_topic,
    'rq': ros_request,
    'rr': ros_reply,
}

object_mapping = {
    'rt': 'ros_topic',
    'rq': 'ros_service',
    'rr': 'ros_service',
}

partition_mapping = {
    'rt': 'ros_topic',
    'rq': 'ros_request',
    'rr': 'ros_reply',
}

mode_mapping = {
    'publication':  {'ros_topic':   'ros_publish',
                     'ros_request': 'ros_call',
                     'ros_reply':   'ros_execute'},
    'subscription': {'ros_topic':   'ros_subscribe',
                     'ros_reply':   'ros_call',
                     'ros_request': 'ros_execute'},
}


def remap(partition, topic):
    namespace = partition[2:]
    if namespace:
        return '/'.join([namespace, topic])
    else:
        return '/' + topic


def create_permission(permission_mode):
    permission = ElementTree.Element(permission_mode)
    return permission


def create_permissions(object_type, object_name_data):
    permissions = ElementTree.Element('permissions')
    permission_modes = set()
    for dds_mode, ros_mode in object_name_data.items():
        permission_modes.add(mode_mapping[dds_mode][ros_mode])
    permission_modes = sorted(permission_modes)
    for permission_mode in permission_modes:
        permission = create_permission(permission_mode)
        permissions.append(permission)
    return permissions


def creat_rule(object_type, attachment, permissions, qualifier, modifier=None):
    rule = ElementTree.Element(object_type)
    rule.set('qualifier', qualifier)
    if modifier:
        rule.set('modifier', modifier)
    rule.append(attachment)
    rule.append(permissions)
    return rule


def create_attachment(expression):
    attachment = ElementTree.Element('attachment')
    attachment.text = expression
    return attachment


def create_profile(name, attachment, modifier=None):
    profile = ElementTree.Element('profile')
    profile.set('name', name)
    if modifier:
        profile.set('modifier', modifier)
    profile.append(attachment)
    return profile


def scrape_objects(objects_, datas, mode):
    for data in datas:
        topic_name = data.findtext("topic_name")  # Could be multiple topics?
        partition_name = data.findtext("partition/name/element")  # Could be multiple partitions?
        ros_mode = partition_name[0:2]
        object_type = object_mapping[ros_mode]
        object_name = object_naming[ros_mode](remap(partition_name, topic_name))
        objects_[object_type][object_name][mode] = partition_mapping[ros_mode]


def get_profile_from_discovery(discovery):
    profile = ElementTree.Element('profile')
    domain_participants = discovery.findall(
        "processes/value/element/domain_participants")
    for domain_participant in domain_participants:
        participant_datas = domain_participant.findall("value/element")
        for participant_data in participant_datas:
            subject_name = '/' + participant_data.findtext(
                "participant_data/participant_name/name")
            attachment = create_attachment(subject_name)
            sub_profile = create_profile(subject_name, attachment)

            object_types = nested_dict()
            publication_datas = participant_data.findall(
                "publications/value/element/publication_data")
            scrape_objects(object_types, publication_datas, 'publication')
            subscription_datas = participant_data.findall(
                "subscriptions/value/element/subscription_data")
            scrape_objects(object_types, subscription_datas, 'subscription')

            for object_type, object_type_data in object_types.items():
                for object_name, object_name_data in object_type_data.items():
                    attachment = create_attachment(object_name)
                    permissions = create_permissions(object_type, object_name_data)
                    qualifer = 'ALLOW'
                    rule = creat_rule(object_type, attachment, permissions, qualifer)
                    sub_profile.append(rule)
            profile.append(sub_profile)
    return profile
