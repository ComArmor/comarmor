# comarmor

[![pypi](https://img.shields.io/pypi/v/comarmor.svg?branch=master)](https://pypi.python.org/pypi/comarmor/)
[![docs](https://readthedocs.org/projects/comarmor/badge/?version=latest)](https://readthedocs.org/projects/comarmor)
[![build](https://travis-ci.org/comarmor/comarmor.svg?branch=master)](https://travis-ci.org/comarmor/comarmor)
[![codecov](https://codecov.io/github/comarmor/comarmor/coverage.svg?branch=master)](https://codecov.io/github/comarmor/comarmor?branch=master)

Comarmor is a configuration language for defining Mandatory Access Control (MAC) policies for communication graphs. comarmor is akin to other MAC systems, yet instead of defining policy profiles for Linux security modules like with [`AppArmor`](https://gitlab.com/apparmor), [`comarmor`](https://github.com/comarmor) defines policy profiles for armoring communications, as the project name's alteration plays upon. comarmor provides users a pluggable configuration language for specifying permissions and governances between objects and subjects by way of attachment expressions, hierarchal structures, and nested importation of compositional profiles, enabling procedurally generated artifacts via [`keymint_tools`](https://github.com/keymint/keymint_tools) for deployments using SROS, or Secure DDS plugins.


## Installation

To install comarmor, the following dependencies must be satisfied:

``` bash
pip3 install lxml
pip3 install xmlschema
```

comarmor can be installed from source using the included `setup.py` file or via pip:

``` bash
pip3 install git+https://github.com/comarmor/comarmor.git@master#egg=comarmor
```

## Example
As a simple example, we'll create a simple policy for SROS2 to enable a `/talker` and `/listener` nodes communicate over the topic `/chatter`. To start with, we'll first create a comarmor profile directory then populate it with comarmor profile files. The exact naming of the directory is unimportant, as they simply need to be consistent for files themselves to afford relative profile include statements later on.

``` bash
mkdir ~/comarmor.d
cd ~/comarmor.d
```

With in the root `comarmor.d` directory, any files found with a `.xml` extension will be parsed into profile objects when the parser is passed the path to `comarmor.d`. Although other profile files nested inside further subdirectories are not immediately considered by the parser, they can still be referenced to, enabling recursive imports and reuse of common permissions. After copying the profile files bellow, the directory structure could be as follows:

``` bash
tree  ~/comarmor.d
comarmor.d/
├── example.xml
├── example_2.xml
├── another_profile_N.xml
└── tunables
    ├── global.xml
    └── node.xml

1 directory, 3 files
```

To add a policy in the root directory, we'll use the comarmor syntax to define a profile file; the XML schema of which can be found in the projects [schema folder](https://github.com/comarmor/comarmor/tree/master/comarmor/schema).

#### `example.xml`

``` xml
<?xml version="1.0" encoding="UTF-8"?>

<profiles xmlns:xi="http://www.w3.org/2001/XInclude">
    <xi:include href="tunables/global.xml" parse="xml"/>
    <profile name="My Talker Profile">
        <attachment>/talker</attachment>
        <xi:include href="tunables/node.xml" parse="xml"/>

        <topic qualifier="ALLOW">
            <attachment>/chatter</attachment>
            <permissions>
                <publish/>
            </permissions>
        </topic>
    </profile>

    <profile name="My Listener Profile">
        <attachment>/listener</attachment>
        <xi:include href="tunables/node.xml" parse="xml"/>

        <topic qualifier="ALLOW">
            <attachment>/chatter</attachment>
            <permissions>
                <subscribe/>
            </permissions>
        </topic>
    </profile>
</profiles>
```

The profile above starts by including some additional elements found in the `global` document, which happens to be in a folder named `tunables`. Next a number of profiles are defined. Profiles are given a name, an attachment, and a scope of further permissions and/or sub profiles. The name is simply used to label the profile for the user when debugging. The attachment is used to define types of subjects the profile is applicable for: this can be formated as an expression. An important note for attachments of sub profiles that any expression used in the sub profile should only be expected to be quired if-and-only-if the attachment of the parent profile matches already. I.e. a child profile can only be applicable if the parent profile is applicable as well.

The permissions can be arbitrary to the object they govern, but should specify a type and designate a qualifier. The qualifier can be either `ALLOW` or `DENY` to permit a MAC framework. Conflicting permission applicable to the same subject that govern the same object will alway conservatively resolving to deny. This enable selective revocation of access after say providing perhaps an overly generous permission, e.g. such as a debugger tool publication access to all topics except those for safety critical E-stop signals.

#### `tunables/node.xml`

``` xml
<?xml version="1.0" encoding="UTF-8"?>

<topic qualifier="ALLOW">
    <attachment>/logout</attachment>
    <permissions>
        <publish/>
    </permissions>
</topic>
```

Imported elements can be as basic as elements within a profile such as a collection of rules as above, or an entire profile. Presently, this is done simply through the user of [XInclude](https://www.w3.org/TR/xinclude/).

#### `tunables/global.xml`

``` xml
<?xml version="1.0" encoding="UTF-8"?>

<profile name="My Logger Profile" xmlns:xi="http://www.w3.org/2001/XInclude">
    <attachment>/logger</attachment>
    <topic qualifier="ALLOW">
        <attachment>/logout</attachment>
        <permissions>
            <publish/>
            <subscribe/>
        </permissions>
    </topic>

    <topic qualifier="ALLOW">
        <attachment>/logout_agg</attachment>
        <permissions>
            <publish/>
        </permissions>
    </topic>
</profile>
```

Additionally, imported elements can have there own imports, allowing you to recursively construct and reuse common elements for any profile.

To parse the profile, we simply pass the profile directory (or exact file) to the comarmor parser. The profiles are expanded and can be manipulated using standard library python XML class objects. Note that the parser checks for schema compliance after expansion, thus syntax error for a profile may originate from included elements rather than from the root profiles.

``` python
import comarmor
from comarmor.xml.utils import beautify_xml
profile_storage = comarmor.parse('~/comarmor.d/')
profile = profile_storage[0]
print(beautify_xml(profile.tree.get_root()))
```

The resulting expanded profile from the parser is printed bellow, including all the permission to publish, subscribe, etc. to satisfy the talker ans listener example.  


#### output

``` xml
<?xml version="1.0" encoding="UTF-8"?>

<profiles>
    <profile name="My Logger Profile" xml:base="tunables/global.xml">
        <attachment>/logger</attachment>
        <topic qualifier="ALLOW" xml:base="tunables/node.xml">
            <attachment>/logout</attachment>
            <permissions>
                <publish/>
                <subscribe/>
            </permissions>
        </topic>

        <topic qualifier="ALLOW">
            <attachment>/logout_agg</attachment>
            <permissions>
                <publish/>
            </permissions>
        </topic>
    </profile>

    <profile name="My Talker Profile">
        <attachment>talker</attachment>
        <topic qualifier="ALLOW" xml:base="tunables/node.xml">
            <attachment>/logout</attachment>
            <permissions>
                <publish/>
            </permissions>
        </topic>

        <topic qualifier="ALLOW">
            <attachment>/chatter</attachment>
            <permissions>
                <publish/>
            </permissions>
        </topic>
    </profile>

    <profile name="My Listener Profile">
        <attachment>listener</attachment>
        <topic qualifier="ALLOW" xml:base="tunables/node.xml">
            <attachment>/logout</attachment>
            <permissions>
                <publish/>
            </permissions>
        </topic>

        <topic qualifier="ALLOW">
            <attachment>/chatter</attachment>
            <permissions>
                <subscribe/>
            </permissions>
        </topic>
    </profile>
</profiles>
```

## TODO
* Support variables
  * Nested scoping
  * Import inheritance
* Improve use of `xml:base` attributes while importing
