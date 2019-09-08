from distutils.core import setup

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

extra_requires = {
    'uvloop': ['uvloop==0.13.0']
}

with open('README.md') as f:
    readme = f.read()

setup(
    name='soundbert',
    author='dsluo',
    url='https://https://github.com/dsluo/SoundBert',
    version='0.1.0',
    description='A soundboard bot for Discord.',
    long_description=readme,
    long_description_content_type='text/markdown',
    include_package_data=True,
    install_requires=requirements,
    extra_requires=extra_requires,
    python_requires='>=3.7',
    py_modules=['soundbert'],
    entry_points='''
        [console_scripts]
        soundbert=soundbert:cli
    '''
)
