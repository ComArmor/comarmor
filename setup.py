from setuptools import find_packages
from setuptools import setup

setup(
    name='comarmor',
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    author='Ruffin White',
    author_email='ruffin@osrfoundation.org',
    maintainer='Ruffin White',
    maintainer_email='ruffin@osrfoundation.org',
    url='https://github.com/comarmor/comarmor/wiki',
    download_url='https://github.com/comarmor/comarmor/releases',
    keywords=['ROS'],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Topic :: Software Development',
    ],
    description='ComArmor is like AppArmor, but for Secure Communications.',
    long_description="""\
ComArmor is a profile interpreter library for policy files,
and provides tooling to create and process access control policies.""",
    license='Apache License, Version 2.0',
    test_suite='test',
    package_data={
        'comarmor': [
            'schema/profile/*',
        ],
    },
)
