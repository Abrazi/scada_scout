"""
SCADA Scout - Setup Script
"""
from setuptools import setup, find_packages
import os

# Read long description from README
def read_long_description():
    here = os.path.abspath(os.path.dirname(__file__))
    try:
        with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "SCADA Protocol Analyzer and Diagnostic Tool"

# Read requirements
def read_requirements():
    here = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(here, 'requirements.txt'), encoding='utf-8') as f:
        requirements = []
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                requirements.append(line)
        return requirements

setup(
    name='scada-scout',
    version='1.0.0',
    description='Cross-Platform SCADA Protocol Analyzer and Diagnostic Tool',
    long_description=read_long_description(),
    long_description_content_type='text/markdown',
    
    author='SCADA Scout Contributors',
    author_email='support@scadascout.example.com',
    url='https://github.com/yourusername/scada-scout',
    
    license='MIT',
    
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: Manufacturing',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering',
        'Topic :: System :: Networking',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Operating System :: OS Independent',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX :: Linux',
        'Operating System :: MacOS :: MacOS X',
    ],
    
    keywords='scada modbus iec61850 iec104 protocol analyzer diagnostic industrial automation',
    
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    
    python_requires='>=3.8',
    
    install_requires=read_requirements(),
    
    extras_require={
        'dev': [
            'pytest>=7.4.0',
            'pytest-qt>=4.2.0',
            'black>=23.0.0',
            'flake8>=6.0.0',
            'mypy>=1.0.0',
        ],
        'iec61850': [
            # Optional: pyiec61850 (requires manual installation)
        ],
        'opc': [
            'opcua>=1.0.0'
        ],
    },
    
    entry_points={
        'console_scripts': [
            'scada-scout=main:main',
        ],
        'gui_scripts': [
            'scada-scout-gui=main:main',
        ],
    },
    
    include_package_data=True,
    
    project_urls={
        'Bug Reports': 'https://github.com/yourusername/scada-scout/issues',
        'Source': 'https://github.com/yourusername/scada-scout',
        'Documentation': 'https://github.com/yourusername/scada-scout/blob/main/README.md',
    },
)
