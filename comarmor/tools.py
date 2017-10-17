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
import sys

import apparmor.ui as aaui
import comarmor.ca as comarmor
from comarmor.common import user_perm, cmd

# setup module translations
from apparmor.translations import init_translation
_ = init_translation()

class ca_tools:
    def __init__(self, tool_name, args):

        self.name = tool_name
        self.profiledir = comarmor.get_full_path(args.dir)
        self.profiling = args.program
        self.check_profile_dir()
        self.silent = None
        comarmor.init_ca(profiledir=self.profiledir)

        if tool_name in ['audit']:
            self.remove = args.remove
        elif tool_name == 'autodep':
            self.force = args.force
            self.aa_mountpoint = comarmor.check_for_comarmor()
        elif tool_name == 'cleanprof':
            self.silent = args.silent

    def check_profile_dir(self):
        if self.profiledir:
            if not os.path.isdir(self.profiledir):
                raise comarmor.ComArmorException("%s is not a directory." % self.profiledir)

        if not user_perm(self.profiledir):
            raise comarmor.ComArmorException("Cannot write to profile directory: %s" % (self.profiledir))

    def get_next_to_profile(self):
        '''Iterator function to walk the list of arguments passed'''

        for p in self.profiling:
            if not p:
                continue

            program = None
            profile = None
            if p.startswith('/'):
                fq_path = p.strip()
                if os.path.commonprefix([comarmor.profile_dir, fq_path]) == comarmor.profile_dir:
                    program = None
                    profile = fq_path
                else:
                    program = fq_path
                    profile = comarmor.get_profile_filename(fq_path)
            else:
                fq_path = p.strip()
                program = None
                profile = fq_path

            yield (program, profile)

    def cleanprof_act(self):
        # used by aa-cleanprof
        comarmor.read_profiles()

        for (program, profile) in self.get_next_to_profile():
            if program is None:
                program = profile

            if not program or not(os.path.exists(program) or comarmor.profile_exists(program)):
                if program and not program.startswith('/'):
                    program = aaui.UI_GetString(_('The given program cannot be found, please try with the fully qualified path name of the program: '), '')
                else:
                    aaui.UI_Info(_("%s does not exist, please double-check the path.") % program)
                    sys.exit(1)

            if program and comarmor.profile_exists(program):
                self.clean_profile(program)

            else:
                if '/' not in program:
                    aaui.UI_Info(_("Can't find %(program)s in the system path list. If the name of the application\nis correct, please run 'which %(program)s' as a user with correct PATH\nenvironment set up in order to find the fully-qualified path and\nuse the full path as parameter.") % { 'program': program })
                else:
                    aaui.UI_Info(_("%s does not exist, please double-check the path.") % program)
                    sys.exit(1)

    def cmd_disable(self):
        comarmor.read_profiles()

        for (program, profile) in self.get_next_to_profile():

            output_name = profile if program is None else program

            if not os.path.isfile(profile) or comarmor.is_skippable_file(profile):
                aaui.UI_Info(_('Profile for %s not found, skipping') % output_name)
                continue

            aaui.UI_Info(_('Disabling %s.') % output_name)
            self.disable_profile(profile)

    def cmd_autodep(self):
        comarmor.read_profiles()

        for (program, profile) in self.get_next_to_profile():
            if not program:
                aaui.UI_Info(_('Please pass an application to generate a profile for, not a profile itself - skipping %s.') % profile)
                continue

            comarmor.check_qualifiers(program)

            if os.path.exists(comarmor.get_profile_filename(program)) and not self.force:
                aaui.UI_Info(_('Profile for %s already exists - skipping.') % program)
            else:
                comarmor.autodep(program)
                if self.aa_mountpoint:
                    comarmor.reload(program)

    def clean_profile(self, program):
        filename = comarmor.get_profile_filename(program)
        import comarmor.cleanprofile as cleanprofile
        prof = cleanprofile.Prof(filename)
        cleanprof = cleanprofile.CleanProf(True, prof, prof)
        deleted = cleanprof.remove_duplicate_rules(program)
        aaui.UI_Info(_("\nDeleted %s rules.") % deleted)
        comarmor.changed[program] = True

        if filename:
            if not self.silent:
                q = aaui.PromptQuestion()
                q.title = 'Changed Local Profiles'
                q.explanation = _('The local profile for %(program)s in file %(file)s was changed. Would you like to save it?') % { 'program': program, 'file': filename }
                q.functions = ['CMD_SAVE_CHANGES', 'CMD_VIEW_CHANGES', 'CMD_ABORT']
                q.default = 'CMD_VIEW_CHANGES'
                q.options = []
                q.selected = 0
                ans = ''
                arg = None
                while ans != 'CMD_SAVE_CHANGES':
                    ans, arg = q.promptUser()
                    if ans == 'CMD_SAVE_CHANGES':
                        comarmor.write_profile_ui_feedback(program)
                    elif ans == 'CMD_VIEW_CHANGES':
                        #oldprofile = comarmor.serialize_profile(comarmor.original_aa[program], program, '')
                        newprofile = comarmor.serialize_profile(comarmor.aa[program], program, '')
                        comarmor.display_changes_with_comments(filename, newprofile)
            else:
                comarmor.write_profile_ui_feedback(program)
        else:
            raise comarmor.AppArmorException(_('The profile for %s does not exists. Nothing to clean.') % program)

    def enable_profile(self, filename):
        comarmor.delete_symlink('disable', filename)

    def disable_profile(self, filename):
        comarmor.create_symlink('disable', filename)
