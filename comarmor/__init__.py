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

"""Library for parsing comarmor profiles and providing an object representation."""

# set version number
try:
    import pkg_resources
    try:
        __version__ = pkg_resources.require('comarmor')[0].version
    except pkg_resources.DistributionNotFound:
        __version__ = 'unset'
    finally:
        del pkg_resources
except ImportError:
    __version__ = 'unset'

import os
import shutil


def parse_profile(path):
    """
    Parse profile from path.

    :param path: The path of the comarmor profile, it may or may not
    include a filename

    :returns: return :class:`ProfileStorage` instance, populated with parsed profiles
    :raises: :exc:`InvalidProfile`
    :raises: :exc:`IOError`
    """
    import os

    if os.path.isfile(path):
        paths = [path]
    elif os.path.exists(path):
        paths = profiles_in(path)
        if not paths:
            raise IOError("Directory '%s' does not contain comarmor profiles" % (path))
    else:
        raise IOError("Path '%s' is neither a directory nor a file" % (path))

    return parse_profile_paths(paths)


def profiles_in(path):
    """
    Finds all profiles that exists at the given path.

    :param path: path to profiles
    :type path: str
    :returns: list of paths to profiles
    :rtype: list
    """
    import os
    paths = []
    for file in os.listdir(path):
        if file.endswith(".xml"):
            paths.append(os.path.join(path, file))

    return paths


def check_schema(schema, data, filename=None):
    from .exceptions import InvalidProfile
    if not schema.is_valid(data):
        try:
            schema.validate(data)
        except Exception as ex:
            if filename is not None:
                msg = "The manifest '%s' contains invalid XML:\n" % filename
            else:
                msg = 'The manifest contains invalid XML:\n'
            raise InvalidProfile(msg + str(ex))


def parse_profile_paths(paths):
    """
    Parse profiles from paths.

    :param paths: full file paths for profiles, ``[str]``
    :returns: return parsed :class:`ProfileStorage`
    :raises: :exc:`InvalidProfile`
    """
    import xmlschema
    from lxml import etree
    from xml.etree import ElementTree

    from .profile import Profile, ProfileStorage
    from .schemas import get_profile_schema_path
    from .xml import utils
    from .exceptions import InvalidProfile

    profile_xsd_path = get_profile_schema_path('comarmor_profile.xsd')
    profile_schema = xmlschema.XMLSchema(profile_xsd_path)

    profile_storage = ProfileStorage()

    for path in paths:
        try:
            # TODO simplify this xinclude workarround
            tree = etree.parse(path)
            tree.xinclude()
            data = etree.tostring(tree)
            root = ElementTree.fromstring(data)
            clean_root = utils.beautify_xml(root)
            data = ElementTree.fromstring(clean_root)

            check_schema(profile_schema, data, filename=path)
            profile_tree = ElementTree.ElementTree(data)
        except InvalidProfile as e:
            e.args = [
                "Invalid profile manifest '%s': %s" %
                (filename, e)]
            raise
        profile = Profile(path=path, tree=profile_tree)
        profile_storage.append(profile)

    return profile_storage
