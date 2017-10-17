# ----------------------------------------------------------------------
#    Copyright (C) 2013 Kshitij Gupta <kgupta8592@gmail.com>
#    Copyright (C) 2014-2017 Christian Boltz <apparmor@cboltz.de>
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


from comarmor.common import ComArmorBug, hasher

from comarmor.rule.topic             import TopicRuleset

ruletypes = {
    'topic':             {'ruleset': TopicRuleset},
}

class ProfileStorage:
    '''class to store the content (header, rules, comments) of a profilename

       Acts like a dict(), but has some additional checks.
    '''

    def __init__(self, profilename, hat, calledby):
        data = dict()

        # self.data['info'] isn't used anywhere, but can be helpful in debugging.
        data['info'] = {'profile': profilename, 'hat': hat, 'calledby': calledby}

        for rule in ruletypes:
            data[rule] = ruletypes[rule]['ruleset']()

        data['alias']            = dict()
        data['include']          = dict()
        data['localinclude']     = dict()
        data['lvar']             = dict()
        data['repo']             = dict()

        data['filename']         = ''
        data['name']             = ''
        data['attachment']       = ''
        data['flags']            = ''
        data['external']         = False
        data['header_comment']   = ''  # currently only set by set_profile_flags()
        data['initial_comment']  = ''
        data['profile_keyword']  = False  # currently only set by set_profile_flags()
        data['profile']          = False  # profile or hat?

        data['allow'] = dict()
        data['deny'] = dict()

        data['allow']['link']    = hasher()
        data['deny']['link']     = hasher()

        # mount, pivot_root, unix have a .get() fallback to list() - initialize them nevertheless
        data['allow']['mount']   = list()
        data['deny']['mount']    = list()
        data['allow']['pivot_root'] = list()
        data['deny']['pivot_root']  = list()
        data['allow']['unix']    = list()
        data['deny']['unix']     = list()

        self.data = data

    def __getitem__(self, key):
        if key in self.data:
            return self.data[key]
        else:
            raise ComArmorBug('attempt to read unknown key %s' % key)

    def __setitem__(self, key, value):
        # TODO: Most of the keys (containing *Ruleset, dict(), list() or hasher()) should be read-only.
        #       Their content needs to be changed, but the container shouldn't
        #       Note: serialize_profile_from_old_profile.write_prior_segments() and write_prior_segments() expect the container to be writeable!
        # TODO: check if value has the expected type
        if key in self.data:
            self.data[key] = value
        else:
            raise ComArmorBug('attempt to set unknown key %s' % key)

    def get(self, key, fallback=None):
        if key in self.data:
            return self.data.get(key, fallback)
        else:
            raise ComArmorBug('attempt to read unknown key %s' % key)
