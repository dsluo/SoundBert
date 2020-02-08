from setuptools import setup, find_packages

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

extras_require = {
    'jishaku': [
        'braceexpand == 0.1.5',
        'import-expression==1.0.0',
        'jishaku == 1.17.1.181'
    ]
}

with open('README.md') as f:
    readme = f.read()

setup(
    name='soundbert',
    author='dsluo',
    url='https://https://github.com/dsluo/SoundBert',
    version='0.2.0',
    description='A soundboard bot for Discord.',
    long_description=readme,
    long_description_content_type='text/markdown',
    include_package_data=True,
    install_requires=requirements,
    extras_require=extras_require,
    python_requires='>=3.8',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'soundbert = soundbert:main'
        ]
    }
)
