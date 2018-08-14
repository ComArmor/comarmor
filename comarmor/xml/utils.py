# Copyright 2017 Open Source Robotics Foundation, Inc.
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

from xml.dom import minidom
from xml.etree import cElementTree as ElementTree


def tidy_xml(element):
    subiter = ElementTree.ElementTree(element).getiterator()
    for x in subiter:
        if len(x):
            if x.text:
                x.text = x.text.strip()
        if x.tail:
            x.tail = x.tail.strip()
    return element


def pretty_xml(element):
    xmlstr = ElementTree.tostring(element, encoding='unicode', method='xml')
    xmlstr = minidom.parseString(xmlstr).toprettyxml(indent='    ', newl='\n', encoding='utf-8')
    return xmlstr.decode('utf-8')


def beautify_xml(elemnt):
    tidy_elemnt = tidy_xml(elemnt)
    pretty_elemnt = pretty_xml(tidy_elemnt)
    return pretty_elemnt
