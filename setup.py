from setuptools import setup

setup(
    name='aclpub_check',
    version='0.1',
    description='Checks formatting of PDF files for *ACL conferences',
    url='https://github.com/acl-org/ACLPUB/',
    author='NAACL 2021 Publication Chairs',
    author_email='naacl2021-publication-chairs@googlegroups.com',
    license='Apache 2.0',
    packages=['aclpub_check'],
    install_requires=[
        'pdfplumber',
        'tqdm',
    ],
    entry_points={
        'console_scripts': ['aclpub_check=aclpub_check.formatchecker:main'],
    },
    zip_safe=False,
)
