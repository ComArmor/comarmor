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

from comarmor.xml.helpers import sort_profiles, compress_profiles


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

prefix_mapping = {
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


def get_permissions(rule):
    permissions = rule.find('permissions')
    if permissions is None:
        permissions = ElementTree.Element('permissions')
        rule.append(permissions)
    return permissions


def set_permissions(rule, permission_mode):
    permissions = get_permissions(rule)
    for permission in permissions:
        if permission.tag == permission_mode:
            return
    else:
        permission = ElementTree.Element(permission_mode)
        permissions.append(permission)


def get_attachments(rule):
    attachments = rule.find('attachments')
    if attachments is None:
        attachments = ElementTree.Element('attachments')
        rule.append(attachments)
    return attachments


def set_attachments(rule, object_name):
    attachments = get_attachments(rule)
    for attachment in attachments:
        if attachment.text == object_name:
            return
    else:
        attachment = ElementTree.Element('attachment')
        attachment.text = object_name
        attachments.append(attachment)


def get_rule(profile, object_type, object_name, qualifier):
    rules = profile.findall(object_type)
    for rule in rules:
        attachment = rule.findtext('attachments/attachment')
        if attachment == object_name and rule.get('qualifier') == qualifier:
            return rule
    else:
        rule = ElementTree.Element(object_type)
        rule.set('qualifier', qualifier)
        set_attachments(rule, object_name)
        profile.append(rule)
        return rule


def set_rule(profile, object_type, object_name, permission_mode, qualifier):
    rule = get_rule(profile, object_type, object_name, qualifier)
    set_permissions(rule, permission_mode)


def set_rules(profile, datas, dds_mode, qualifier):
    for data in datas:
        topic_name = data.findtext("topic_name")
        ros_mode = topic_name[0:2]
        object_type = object_mapping[ros_mode]
        object_name = object_naming[ros_mode](topic_name[2:])
        permission_mode = mode_mapping[dds_mode][prefix_mapping[ros_mode]]
        set_rule(profile, object_type, object_name, permission_mode, qualifier)


def get_profile(root, name):
    profiles = root.findall('profile')
    for profile in profiles:
        if profile.get('name') == name:
            return profile
    else:
        profile = ElementTree.Element('profile')
        profile.set('name', name)
        root.append(profile)
        return profile


def get_profile_from_discovery(discovery):
    profiles = ElementTree.Element('profiles')
    domain_participants = discovery.findall(
        "processes/value/element/domain_participants/value/element")
    for domain_participant in domain_participants:
        subject_name = '/' + domain_participant.findtext(
            "participant_data/participant_name/name")
        profile = get_profile(profiles, subject_name)
        set_attachments(profile, subject_name)

        publication_datas = domain_participant.findall(
            "publications/value/element/publication_data")
        set_rules(profile, publication_datas, 'publication', 'ALLOW')
        subscription_datas = domain_participant.findall(
            "subscriptions/value/element/subscription_data")
        set_rules(profile, subscription_datas, 'subscription', 'ALLOW')

    profiles = compress_profiles(profiles)
    sort_profiles(profiles)
    return profiles
