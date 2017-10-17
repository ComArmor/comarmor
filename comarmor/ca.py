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

import os
import re
import shutil
import tempfile
import time

from copy import deepcopy

import apparmor.config
# import apparmor.logparser
# import apparmor.severity


import apparmor.ui as aaui
from apparmor.aare import AARE

from comarmor.common import (
    ComArmorBug,
    ComArmorException,
    DebugLogger,
    hasher,
    open_file_read,
    open_file_write,
    valid_path,
)

from apparmor.regex import (RE_PROFILE_START, RE_PROFILE_END, RE_PROFILE_LINK,
                            RE_PROFILE_ALIAS,
                            RE_PROFILE_BOOLEAN, RE_PROFILE_VARIABLE, RE_PROFILE_CONDITIONAL,
                            RE_PROFILE_CONDITIONAL_VARIABLE, RE_PROFILE_CONDITIONAL_BOOLEAN,
                            RE_PROFILE_CHANGE_HAT,
                            RE_PROFILE_HAT_DEF, RE_PROFILE_MOUNT,
                            RE_PROFILE_PIVOT_ROOT,
                            RE_PROFILE_UNIX, RE_RULE_HAS_COMMA, RE_HAS_COMMENT_SPLIT,
                            strip_quotes, parse_profile_start_line, re_match_include)

import comarmor.rules as ca_rules

from comarmor.profile_storage import ProfileStorage, ruletypes
from comarmor.rule import quote_if_needed
from comarmor.rule.topic import TopicRule


# setup module translations
from apparmor.translations import init_translation
_ = init_translation()


# Setup logging incase of debugging is enabled
debug_logger = DebugLogger('ca')

# The database for severity
sev_db = None
# The file to read log messages from
### Was our
logfile = None

CONFDIR = None
conf = None
cfg = None
repo_cfg = None

parser = None
profile_dir = None
extra_profile_dir = None
### end our
# To keep track of previously included profile fragments
include = dict()

existing_profiles = dict()

# To store the globs entered by users so they can be provided again
# format: user_globs['/foo*'] = AARE('/foo*')
user_globs = {}

## Variables used under logprof
transitions = hasher()

ca = hasher()  # Profiles originally in sd, replace by aa
original_ca = hasher()
extras = hasher()  # Inactive profiles from extras
### end our
log_pid = dict()  # handed over to ReadLog, gets filled in logparser.py. The only case the previous content of this variable _might_(?) be used is aa-genprof (multiple do_logprof_pass() runs)

profile_changes = hasher()
prelog = hasher()
changed = dict()
created = []
helpers = dict()  # Preserve this between passes # was our
### logprof ends

filelist = hasher()    # File level variables and stuff in config files


from apparmor.aa import (
    get_full_path,
)


def attach_profile_data(profiles, profile_data):
    # Make deep copy of data to avoid changes to
    # arising due to mutables
    for p in profile_data.keys():
        if profiles.get(p, False):
            for hat in profile_data[p].keys():
                if profiles[p].get(hat, False):
                    raise ComArmorException(_("Conflicting profiles for %s defined in two files:\n- %s\n- %s") %
                            (combine_name(p, hat), profiles[p][hat]['filename'], profile_data[p][hat]['filename']))

        profiles[p] = deepcopy(profile_data[p])


def delete_duplicates(profile, incname):
    deleted = 0
    # Allow rules covered by denied rules shouldn't be deleted
    # only a subset allow rules may actually be denied

    if include.get(incname, False):
        for rule_type in ruletypes:
            deleted += profile[rule_type].delete_duplicates(include[incname][incname][rule_type])

    elif filelist.get(incname, False):
        for rule_type in ruletypes:
            deleted += profile[rule_type].delete_duplicates(filelist[incname][incname][rule_type])

    return deleted


def get_include_data(filename):
    data = []
    filename = profile_dir + '/' + filename
    if os.path.exists(filename):
        with open_file_read(filename) as f_in:
            data = f_in.readlines()
    else:
        raise AppArmorException(_('File Not Found: %s') % filename)
    return data


def get_profile_filename(profile):
    """Returns the full profile name"""
    if existing_profiles.get(profile, False):
        return existing_profiles[profile]
    elif profile.startswith('/'):
        # Remove leading /
        profile = profile[1:]
    else:
        profile = "profile_" + profile
    profile = profile.replace('/', '.')
    full_profilename = profile_dir + '/' + profile
    return full_profilename


def include_dir_filelist(profile_dir, include_name):
    '''returns a list of files in the given profile_dir/include_name directory, except skippable files'''
    files = []
    for path in os.listdir(profile_dir + '/' + include_name):
        path = path.strip()
        if is_skippable_file(path):
            continue
        if os.path.isfile(profile_dir + '/' + include_name + '/' + path):
            file_name = include_name + '/' + path
            file_name = file_name.replace(profile_dir + '/', '')
            files.append(file_name)

    return files


def is_skippable_file(path):
    """Returns True if filename matches something to be skipped (rpm or dpkg backup files, hidden files etc.)
        The list of skippable files needs to be synced with apparmor initscript and libapparmor _aa_is_blacklisted()
        path: filename (with or without directory)"""

    basename = os.path.basename(path)

    if not basename or basename[0] == '.' or basename == 'README':
        return True

    skippable_suffix = ('.dpkg-new', '.dpkg-old', '.dpkg-dist', '.dpkg-bak', '.rpmnew', '.rpmsave', '.orig', '.rej', '~')
    if basename.endswith(skippable_suffix):
        return True

    return False


def load_include(incname):
    load_includeslist = [incname]
    while load_includeslist:
        incfile = load_includeslist.pop(0)
        if include.get(incfile, {}).get(incfile, False):
            pass  # already read, do nothing
        elif os.path.isfile(profile_dir + '/' + incfile):
            data = get_include_data(incfile)
            incdata = parse_profile_data(data, incfile, True)
            attach_profile_data(include, incdata)
        #If the include is a directory means include all subfiles
        elif os.path.isdir(profile_dir + '/' + incfile):
            load_includeslist += include_dir_filelist(profile_dir, incfile)
        else:
            raise AppArmorException("Include file %s not found" % (profile_dir + '/' + incfile) )

    return 0


def parse_profile_data(data, file, do_include):
    profile_data = hasher()
    profile = None
    hat = None
    in_contained_hat = None
    repo_data = None
    parsed_profiles = []
    initial_comment = ''
    lastline = None

    if do_include:
        profile = file
        hat = file
        profile_data[profile][hat] = ProfileStorage(profile, hat, 'parse_profile_data() do_include')
        profile_data[profile][hat]['filename'] = file

    for lineno, line in enumerate(data):
        line = line.strip()
        if not line:
            continue
        # we're dealing with a multiline statement
        if lastline:
            line = '%s %s' % (lastline, line)
            lastline = None
        # Starting line of a profile
        if RE_PROFILE_START.search(line):
            (profile, hat, attachment, flags, in_contained_hat, pps_set_profile, pps_set_hat_external) = parse_profile_start(line, file, lineno, profile, hat)

            if profile_data[profile].get(hat, False):
                raise AppArmorException('Profile %(profile)s defined twice in %(file)s, last found in line %(line)s' %
                    { 'file': file, 'line': lineno + 1, 'profile': combine_name(profile, hat) })

            profile_data[profile][hat] = ProfileStorage(profile, hat, 'parse_profile_data() profile_start')

            if attachment:
                profile_data[profile][hat]['attachment'] = attachment
            if pps_set_profile:
                profile_data[profile][hat]['profile'] = True
            if pps_set_hat_external:
                profile_data[profile][hat]['external'] = True

            # Profile stored
            existing_profiles[profile] = file

            # save profile name and filename
            profile_data[profile][hat]['name'] = profile
            profile_data[profile][hat]['filename'] = file
            filelist[file]['profiles'][profile][hat] = True

            profile_data[profile][hat]['flags'] = flags

            # Save the initial comment
            if initial_comment:
                profile_data[profile][hat]['initial_comment'] = initial_comment

            initial_comment = ''

            if repo_data:
                profile_data[profile][profile]['repo']['url'] = repo_data['url']
                profile_data[profile][profile]['repo']['user'] = repo_data['user']

        elif RE_PROFILE_END.search(line):
            # If profile ends and we're not in one
            if not profile:
                raise ComArmorException(_('Syntax Error: Unexpected End of Profile reached in file: %(file)s line: %(line)s') % { 'file': file, 'line': lineno + 1 })

            if in_contained_hat:
                hat = profile
                in_contained_hat = False
            else:
                parsed_profiles.append(profile)
                profile = None

            initial_comment = ''

        elif RE_PROFILE_LINK.search(line):
            matches = RE_PROFILE_LINK.search(line).groups()

            if not profile:
                raise ComArmorException(_('Syntax Error: Unexpected link entry found in file: %(file)s line: %(line)s') % { 'file': file, 'line': lineno + 1 })

            audit = False
            if matches[0]:
                audit = True

            allow = 'allow'
            if matches[1] and matches[1].strip() == 'deny':
                allow = 'deny'

            subset = matches[3]
            link = strip_quotes(matches[6])
            value = strip_quotes(matches[7])
            profile_data[profile][hat][allow]['link'][link]['to'] = value
            profile_data[profile][hat][allow]['link'][link]['mode'] = profile_data[profile][hat][allow]['link'][link].get('mode', set()) | apparmor.aamode.AA_MAY_LINK

            if subset:
                profile_data[profile][hat][allow]['link'][link]['mode'] |= apparmor.aamode.AA_LINK_SUBSET

            if audit:
                profile_data[profile][hat][allow]['link'][link]['audit'] = profile_data[profile][hat][allow]['link'][link].get('audit', set()) | apparmor.aamode.AA_LINK_SUBSET
            else:
                profile_data[profile][hat][allow]['link'][link]['audit'] = set()

        elif RE_PROFILE_ALIAS.search(line):
            matches = RE_PROFILE_ALIAS.search(line).groups()

            from_name = strip_quotes(matches[0])
            to_name = strip_quotes(matches[1])

            if profile:
                profile_data[profile][hat]['alias'][from_name] = to_name
            else:
                if not filelist.get(file, False):
                    filelist[file] = hasher()
                filelist[file]['alias'][from_name] = to_name

        elif RE_PROFILE_BOOLEAN.search(line):
            matches = RE_PROFILE_BOOLEAN.search(line).groups()

            if profile and not do_include:
                raise AppArmorException(_('Syntax Error: Unexpected boolean definition found inside profile in file: %(file)s line: %(line)s') % {
                        'file': file, 'line': lineno + 1 })

            bool_var = matches[0]
            value = matches[1]

            profile_data[profile][hat]['lvar'][bool_var] = value

        elif RE_PROFILE_VARIABLE.search(line):
            # variable additions += and =
            matches = RE_PROFILE_VARIABLE.search(line).groups()

            list_var = strip_quotes(matches[0])
            var_operation = matches[1]
            value = matches[2]

            if profile:
                if not profile_data[profile][hat].get('lvar', False):
                    profile_data[profile][hat]['lvar'][list_var] = []
                store_list_var(profile_data[profile]['lvar'], list_var, value, var_operation, file)
            else:
                if not filelist[file].get('lvar', False):
                    filelist[file]['lvar'][list_var] = []
                store_list_var(filelist[file]['lvar'], list_var, value, var_operation, file)

        elif RE_PROFILE_CONDITIONAL.search(line):
            # Conditional Boolean
            pass

        elif RE_PROFILE_CONDITIONAL_VARIABLE.search(line):
            # Conditional Variable defines
            pass

        elif RE_PROFILE_CONDITIONAL_BOOLEAN.search(line):
            # Conditional Boolean defined
            pass

        elif re_match_include(line):
            # Include files
            include_name = re_match_include(line)
            if include_name.startswith('local/'):
                profile_data[profile][hat]['localinclude'][include_name] = True

            if profile:
                profile_data[profile][hat]['include'][include_name] = True
            else:
                if not filelist.get(file):
                    filelist[file] = hasher()
                filelist[file]['include'][include_name] = True
            # If include is a directory
            if os.path.isdir(profile_dir + '/' + include_name):
                for file_name in include_dir_filelist(profile_dir, include_name):
                    if not include.get(file_name, False):
                        load_include(file_name)
            else:
                if not include.get(include_name, False):
                    load_include(include_name)

        elif RE_PROFILE_PIVOT_ROOT.search(line):
            matches = RE_PROFILE_PIVOT_ROOT.search(line).groups()

            if not profile:
                raise ComArmorException(_('Syntax Error: Unexpected pivot_root entry found in file: %(file)s line: %(line)s') % { 'file': file, 'line': lineno + 1 })

            audit = False
            if matches[0]:
                audit = True
            allow = 'allow'
            if matches[1] and matches[1].strip() == 'deny':
                allow = 'deny'
            pivot_root = matches[2].strip()

            pivot_root_rule = parse_pivot_root_rule(pivot_root)
            pivot_root_rule.audit = audit
            pivot_root_rule.deny = (allow == 'deny')

            pivot_root_rules = profile_data[profile][hat][allow].get('pivot_root', list())
            pivot_root_rules.append(pivot_root_rule)
            profile_data[profile][hat][allow]['pivot_root'] = pivot_root_rules

        elif RE_PROFILE_CHANGE_HAT.search(line):
            matches = RE_PROFILE_CHANGE_HAT.search(line).groups()

            if not profile:
                raise AppArmorException(_('Syntax Error: Unexpected change hat declaration found in file: %(file)s line: %(line)s') % { 'file': file, 'line': lineno + 1 })

            aaui.UI_Important(_('Ignoring no longer supported change hat declaration "^%(hat)s," found in file: %(file)s line: %(line)s') % {
                    'hat': matches[0], 'file': file, 'line': lineno + 1 })

        elif RE_PROFILE_HAT_DEF.search(line):
            # An embedded hat syntax definition starts
            matches = RE_PROFILE_HAT_DEF.search(line)
            if not profile:
                raise AppArmorException(_('Syntax Error: Unexpected hat definition found in file: %(file)s line: %(line)s') % { 'file': file, 'line': lineno + 1 })

            in_contained_hat = True
            hat = matches.group('hat')
            hat = strip_quotes(hat)

            # if hat is already known, the filelist check some lines below will error out.
            # nevertheless, just to be sure, don't overwrite existing profile_data.
            if not profile_data[profile].get(hat, False):
                profile_data[profile][hat] = ProfileStorage(profile, hat, 'parse_profile_data() hat_def')
                profile_data[profile][hat]['filename'] = file

            flags = matches.group('flags')

            profile_data[profile][hat]['flags'] = flags

            if initial_comment:
                profile_data[profile][hat]['initial_comment'] = initial_comment
            initial_comment = ''
            if filelist[file]['profiles'][profile].get(hat, False) and not do_include:
                raise AppArmorException(_('Error: Multiple definitions for hat %(hat)s in profile %(profile)s.') % { 'hat': hat, 'profile': profile })
            filelist[file]['profiles'][profile][hat] = True

        elif line[0] == '#':
            # Handle initial comments
            if not profile:
                if line.startswith('# Last Modified:'):
                    continue
                elif line.startswith('# REPOSITORY:'): # TODO: allow any number of spaces/tabs
                    parts = line.split()
                    if len(parts) == 3 and parts[2] == 'NEVERSUBMIT':
                        repo_data = {'neversubmit': True}
                    elif len(parts) == 5:
                        repo_data = {'url': parts[2],
                                     'user': parts[3],
                                     'id': parts[4]}
                    else:
                        aaui.UI_Important(_('Warning: invalid "REPOSITORY:" line in %s, ignoring.') % file)
                        initial_comment = initial_comment + line + '\n'
                else:
                    initial_comment = initial_comment + line + '\n'

        elif TopicRule.match(line):
            # leading permissions could look like a keyword, therefore handle topic rules after everything else
            if not profile:
                raise ComArmorException(_('Syntax Error: Unexpected path entry found in topic: %(file)s line: %(line)s') % { 'file': file, 'line': lineno + 1 })

            profile_data[profile][hat]['topic'].add(TopicRule.parse(line))

        elif not RE_RULE_HAS_COMMA.search(line):
            # Bah, line continues on to the next line
            if RE_HAS_COMMENT_SPLIT.search(line):
                # filter trailing comments
                lastline = RE_HAS_COMMENT_SPLIT.search(line).group('not_comment')
            else:
                lastline = line
        else:
            raise ComArmorException(_('Syntax Error: Unknown line found in file %(file)s line %(lineno)s:\n    %(line)s') % { 'file': file, 'lineno': lineno + 1, 'line': line })

    # Below is not required I'd say
    if not do_include:
        for hatglob in cfg['required_hats'].keys():
            for parsed_prof in sorted(parsed_profiles):
                if re.search(hatglob, parsed_prof):
                    for hat in cfg['required_hats'][hatglob].split():
                        if not profile_data[parsed_prof].get(hat, False):
                            profile_data[parsed_prof][hat] = ProfileStorage(parsed_prof, hat, 'parse_profile_data() required_hats')

    # End of file reached but we're stuck in a profile
    if profile and not do_include:
        raise AppArmorException(_("Syntax Error: Missing '}' or ','. Reached end of file %(file)s while inside profile %(profile)s") % { 'file': file, 'profile': profile })

    return profile_data


def parse_profile_start(line, file, lineno, profile, hat):
    matches = parse_profile_start_line(line, file)

    if profile:  # we are inside a profile, so we expect a child profile
        if not matches['profile_keyword']:
            raise AppArmorException(_('%(profile)s profile in %(file)s contains syntax errors in line %(line)s: missing "profile" keyword.') % {
                    'profile': profile, 'file': file, 'line': lineno + 1 })
        if profile != hat:
            # nesting limit reached - a child profile can't contain another child profile
            raise AppArmorException(_('%(profile)s profile in %(file)s contains syntax errors in line %(line)s: a child profile inside another child profile is not allowed.') % {
                    'profile': profile, 'file': file, 'line': lineno + 1 })

        hat = matches['profile']
        in_contained_hat = True
        pps_set_profile = True
        pps_set_hat_external = False

    else:  # stand-alone profile
        profile = matches['profile']
        if len(profile.split('//')) >= 2:
            profile, hat = profile.split('//')[:2]
            pps_set_hat_external = True
        else:
            hat = profile
            pps_set_hat_external = False

        in_contained_hat = False
        pps_set_profile = False

    attachment = matches['attachment']
    flags = matches['flags']

    return (profile, hat, attachment, flags, in_contained_hat, pps_set_profile, pps_set_hat_external)


def profile_exists(program):
    """Returns True if profile exists, False otherwise"""
    # Check cache of profiles

    if existing_profiles.get(program, False):
        return True
    # Check the disk for profile
    prof_path = get_profile_filename(program)
    #print(prof_path)
    if os.path.isfile(prof_path):
        # Add to cache of profile
        existing_profiles[program] = prof_path
        return True
    return False


def read_profile(file, active_profile):
    data = None
    try:
        with open_file_read(file) as f_in:
            data = f_in.readlines()
    except IOError:
        debug_logger.debug("read_profile: can't read %s - skipping" % file)
        return None

    profile_data = parse_profile_data(data, file, 0)

    if profile_data and active_profile:
        attach_profile_data(ca, profile_data)
        attach_profile_data(original_ca, profile_data)
    elif profile_data:
        attach_profile_data(extras, profile_data)


def read_profiles():
    # we'll read all profiles from disk, so reset the storage first (autodep() might have created/stored
    # a profile already, which would cause a 'Conflicting profile' error in attach_profile_data())
    global ca, original_ca
    ca = hasher()
    original_ca = hasher()

    try:
        os.listdir(profile_dir)
    except:
        fatal_error(_("Can't read ComArmor profiles in %s") % profile_dir)

    for file in os.listdir(profile_dir):
        if os.path.isfile(profile_dir + '/' + file):
            if is_skippable_file(file):
                continue
            else:
                read_profile(profile_dir + '/' + file, True)


def separate_vars(vs):
    """Returns a list of all the values for a variable"""
    data = set()
    vs = vs.strip()

    RE_VARS = re.compile('^(("[^"]*")|([^"\s]+))\s*(.*)$')
    while RE_VARS.search(vs):
        matches = RE_VARS.search(vs).groups()
        data.add(strip_quotes(matches[0]))
        vs = matches[3].strip()

    if vs:
        raise AppArmorException('Variable assignments contains invalid parts (unbalanced quotes?): %s' % vs)

    return data


def serialize_profile(profile_data, name, options):
    string = ''
    include_metadata = False
    include_flags = True
    data = []

    if options:  # and type(options) == dict:
        if options.get('METADATA', False):
            include_metadata = True
        if options.get('NO_FLAGS', False):
            include_flags = False

    if include_metadata:
        string = '# Last Modified: %s\n' % time.asctime()

        if (profile_data[name].get('repo', False) and
                profile_data[name]['repo']['url'] and
                profile_data[name]['repo']['user'] and
                profile_data[name]['repo']['id']):
            repo = profile_data[name]['repo']
            string += '# REPOSITORY: %s %s %s\n' % (repo['url'], repo['user'], repo['id'])
        elif profile_data[name]['repo'].get('neversubmit'):
            string += '# REPOSITORY: NEVERSUBMIT\n'

    #     if profile_data[name].get('initial_comment', False):
    #         comment = profile_data[name]['initial_comment']
    #         comment.replace('\\n', '\n')
    #         string += comment + '\n'

    prof_filename = get_profile_filename(name)
    if filelist.get(prof_filename, False):
        data += write_alias(filelist[prof_filename], 0)
        data += write_list_vars(filelist[prof_filename], 0)
        data += write_includes(filelist[prof_filename], 0)

    #Here should be all the profiles from the files added write after global/common stuff
    for prof in sorted(filelist[prof_filename]['profiles'].keys()):
        if prof != name:
            if original_ca[prof][prof].get('initial_comment', False):
                comment = original_ca[prof][prof]['initial_comment']
                comment.replace('\\n', '\n')
                data += [comment + '\n']
            data += write_piece(original_ca[prof], 0, prof, prof, include_flags)
        else:
            if profile_data[name].get('initial_comment', False):
                comment = profile_data[name]['initial_comment']
                comment.replace('\\n', '\n')
                data += [comment + '\n']
            data += write_piece(profile_data, 0, name, name, include_flags)

    string += '\n'.join(data)

    return string + '\n'


def set_ref_allow(prof_data, allow):
    if allow:
        return prof_data[allow], set_allow_str(allow)
    else:
        return prof_data, ''


def store_list_var(var, list_var, value, var_operation, filename):
    """Store(add new variable or add values to variable) the variables encountered in the given list_var
       - the 'var' parameter will be modified
       - 'list_var' is the variable name, for example '@{foo}'
        """
    vlist = separate_vars(value)
    if var_operation == '=':
        if not var.get(list_var, False):
            var[list_var] = set(vlist)
        else:
            raise AppArmorException(_('Redefining existing variable %(variable)s: %(value)s in %(file)s') % { 'variable': list_var, 'value': value, 'file': filename })
    elif var_operation == '+=':
        if var.get(list_var, False):
            var[list_var] |= vlist
        else:
            raise AppArmorException(_('Values added to a non-existing variable %(variable)s: %(value)s in %(file)s') % { 'variable': list_var, 'value': value, 'file': filename })
    else:
        raise AppArmorException(_('Unknown variable operation %(operation)s for variable %(variable)s in %(file)s') % { 'operation': var_operation, 'variable': list_var, 'file': filename })


def write_alias(prof_data, depth):
    return write_pair(prof_data, depth, '', 'alias', 'alias ', ' -> ', ',', quote_if_needed)


def write_header(prof_data, depth, name, embedded_hat, write_flags):
    pre = ' ' * int(depth * 2)
    data = []
    unquoted_name = name
    name = quote_if_needed(name)

    attachment = ''
    if prof_data['attachment']:
        attachment = ' %s' % quote_if_needed(prof_data['attachment'])

    comment = ''
    if prof_data['header_comment']:
        comment = ' %s' % prof_data['header_comment']

    if (not embedded_hat and re.search('^[^/]', unquoted_name)) or (embedded_hat and re.search('^[^^]', unquoted_name)) or prof_data['attachment'] or prof_data['profile_keyword']:
        name = 'profile %s%s' % (name, attachment)

    flags = ''
    if write_flags and prof_data['flags']:
        flags = ' flags=(%s)' % prof_data['flags']

    data.append('%s%s%s {%s' % (pre, name, flags, comment))

    return data


def write_includes(prof_data, depth):
    return write_single(prof_data, depth, '', 'include', '#include <', '>')


def write_list_vars(prof_data, depth):
    return write_pair(prof_data, depth, '', 'lvar', '', ' = ', '', var_transform)


def write_pair(prof_data, depth, allow, name, prefix, sep, tail, fn):
    pre = '  ' * depth
    data = []
    ref, allow = set_ref_allow(prof_data, allow)

    if ref.get(name, False):
        for key in sorted(ref[name].keys()):
            value = fn(ref[name][key])  # eval('%s(%s)' % (fn, ref[name][key]))
            data.append('%s%s%s%s%s%s' % (pre, allow, prefix, key, sep, value))
        if ref[name].keys():
            data.append('')

    return data


def write_piece(profile_data, depth, name, nhat, write_flags):
    pre = '  ' * depth
    data = []
    wname = None
    inhat = False
    if name == nhat:
        wname = name
    else:
        wname = name + '//' + nhat
        name = nhat
        inhat = True
    data += write_header(profile_data[name], depth, wname, False, write_flags)
    data += write_rules(profile_data[name], depth + 1)

    pre2 = '  ' * (depth + 1)

    if not inhat:
        # Embedded hats
        for hat in list(filter(lambda x: x != name, sorted(profile_data.keys()))):
            if not profile_data[hat]['external']:
                data.append('')
                if profile_data[hat]['profile']:
                    data += list(map(str, write_header(profile_data[hat], depth + 1, hat, True, write_flags)))
                else:
                    data += list(map(str, write_header(profile_data[hat], depth + 1, '^' + hat, True, write_flags)))

                data += list(map(str, write_rules(profile_data[hat], depth + 2)))

                data.append('%s}' % pre2)

        data.append('%s}' % pre)

        # External hats
        for hat in list(filter(lambda x: x != name, sorted(profile_data.keys()))):
            if name == nhat and profile_data[hat].get('external', False):
                data.append('')
                data += list(map(lambda x: '  %s' % x, write_piece(profile_data, depth - 1, name, nhat, write_flags)))
                data.append('  }')

    return data


def write_profile(profile):
    prof_filename = None
    if ca[profile][profile].get('filename', False):
        prof_filename = ca[profile][profile]['filename']
    else:
        prof_filename = get_profile_filename(profile)

    newprof = tempfile.NamedTemporaryFile('w', suffix='~', delete=False, dir=profile_dir)
    if os.path.exists(prof_filename):
        shutil.copymode(prof_filename, newprof.name)
    else:
        #permission_600 = stat.S_IRUSR | stat.S_IWUSR    # Owner read and write
        #os.chmod(newprof.name, permission_600)
        pass

    serialize_options = {}
    serialize_options['METADATA'] = True

    profile_string = serialize_profile(ca[profile], profile, serialize_options)
    newprof.write(profile_string)
    newprof.close()

    os.rename(newprof.name, prof_filename)

    if profile in changed:
        changed.pop(profile)
    else:
        debug_logger.info("Unchanged profile written: %s (not listed in 'changed' list)" % profile)

    original_ca[profile] = deepcopy(ca[profile])


def write_profile_ui_feedback(profile):
    aaui.UI_Info(_('Writing updated profile for %s.') % profile)
    write_profile(profile)


def write_rules(prof_data, depth):
    data = write_alias(prof_data, depth)
    data += write_list_vars(prof_data, depth)
    data += write_includes(prof_data, depth)
    # data += write_capabilities(prof_data, depth)
    data += write_topic(prof_data, depth)

    return data


def write_single(prof_data, depth, allow, name, prefix, tail):
    pre = '  ' * depth
    data = []
    ref, allow = set_ref_allow(prof_data, allow)

    if ref.get(name, False):
        for key in sorted(ref[name].keys()):
            qkey = quote_if_needed(key)
            data.append('%s%s%s%s%s' % (pre, allow, prefix, qkey, tail))
        if ref[name].keys():
            data.append('')

    return data


def write_topic(prof_data, depth):
    data = []
    if prof_data.get('topic', False):
        data = prof_data['topic'].get_clean(depth)
    return data


def var_transform(ref):
    data = []
    for value in ref:
        if not value:
            value = '""'
        data.append(quote_if_needed(value))
    return ' '.join(data)


def init_ca(confdir="/etc/comarmor", profiledir=None):
    global CONFDIR
    global conf
    global cfg
    global profile_dir
    global extra_profile_dir

    if CONFDIR:
        # config already initialized (and possibly changed afterwards),
        # so don't overwrite the config variables
        return

    CONFDIR = confdir
    conf = apparmor.config.Config('ini', CONFDIR)
    cfg = conf.read_config('logprof.conf')

    # prevent various failures if logprof.conf doesn't exist
    if not cfg.sections():
        cfg.add_section('settings')
        cfg.add_section('required_hats')

    if cfg['settings'].get('default_owner_prompt', False):
        cfg['settings']['default_owner_prompt'] = ''

    if not profiledir:
        profile_dir = conf.find_first_dir(
            cfg['settings'].get('profiledir')) or '/etc/comarmor.d'
    else:
        profile_dir = profiledir

    if not os.path.isdir(profile_dir):
        raise ComArmorException(
            "Can't find ComArmor profiles in %s" % (profile_dir))

    extra_profile_dir = conf.find_first_dir(cfg['settings'].get(
        'inactive_profiledir')) or '/usr/share/comarmor/extra-profiles/'
