from setuptools import setup, find_packages

# with open('requirements.txt') as f:
#     requirements = f.read().splitlines()
requirements = [
    'aiofiles==0.4.0',
    'aiohttp==3.5.4',
    'async-timeout==3.0.1',
    'asyncpg==0.19.0',
    'attrs==19.3.0',
    'cffi==1.13.0',
    'chardet==3.0.4',
    'Click==7.0',
    'discord.py==1.3.0a2107+gc6539bb',
    'idna==2.8',
    'multidict==4.5.2',
    'pycparser==2.19',
    'PyNaCl==1.3.0',
    'six==1.12.0',
    'toml==0.10.0',
    'websockets==6.0',
    'yarl==1.3.0',
    'youtube-dl==2019.10.16',
]

extras_require = {
    'uvloop': ['uvloop==0.13.0']
}

with open('README.md') as f:
    readme = f.read()

setup(
    name='soundbert',
    author='dsluo',
    url='https://https://github.com/dsluo/SoundBert',
    version='0.1.1',
    description='A soundboard bot for Discord.',
    long_description=readme,
    long_description_content_type='text/markdown',
    include_package_data=True,
    install_requires=requirements,
    extras_require=extras_require,
    python_requires='>=3.7',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'soundbert = soundbert:cli'
        ]
    }
)
