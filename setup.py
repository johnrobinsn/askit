from setuptools import setup, find_packages

setup(
    name='askit',
    version='0.1',
    packages=find_packages(include=['askit', 'askit.*']),
    install_requires=[
        'python-dotenv',
        'openai',
        'termcolor',
        'mcp[cli]',
        'prompt_toolkit',
        'json5'
    ],
    entry_points={
        'console_scripts': [
            'get_current_weather=askit.main:main',
        ],
    },
    author='John Robinson',
    author_email='johnrobinsn@gmail.com',
    description='A module to ask any one question and get an answer.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    # url='https://github.com/yourusername/your_project',
    # classifiers=[
    #     'Programming Language :: Python :: 3',
    #     'License :: OSI Approved :: MIT License',
    #     'Operating System :: OS Independent',
    # ],
    python_requires='>=3.11',
)