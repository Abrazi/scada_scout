# SCADA Scout - .gitignore

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
pip-wheel-metadata/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual Environments
venv/
venv-dev/
venv-pypy/
.venv/
env/
ENV/
env.bak/
venv.bak/

# IDEs
.idea/
.vscode/
*.swp
*.swo
*~
.DS_Store
*.sublime-project
*.sublime-workspace

# PyCharm
.idea/
*.iml

# VS Code
.vscode/
*.code-workspace

# Jupyter Notebook
.ipynb_checkpoints

# pyenv
.python-version

# Testing
.pytest_cache/
.tox/
.coverage
.coverage.*
htmlcov/
.hypothesis/

# Logs
*.log
logs/

# Database
*.db
*.sqlite
*.sqlite3

# Configuration files (user-specific)
config.json
*.ini
*.cfg

# Temporary files
*.tmp
*.temp
*.bak
*.backup

# OS specific
Thumbs.db
.DS_Store
desktop.ini

# SCD/SCL files (project specific - user data)
*.scd
*.scl
*.cid
*.icd
# Exception: Keep test files
!test*.scd
!test*.scl

# Export files
exports/
network_scripts/
*.bat.bak
*.sh.bak

# Documentation build
docs/_build/
docs/.doctrees/

# Distribution / Packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# PyInstaller
*.manifest
*.spec

# Installer logs
pip-log.txt
pip-delete-this-directory.txt

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/
cover/

# Translations
*.mo
*.pot

# Sphinx documentation
docs/_build/

# PyBuilder
.pybuilder/
target/

# IPython
profile_default/
ipython_config.py

# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Rope project settings
.ropeproject

# mkdocs documentation
/site

# mypy
.mypy_cache/
.dmypy.json
dmypy.json

# Pyre type checker
.pyre/

# pytype static type analyzer
.pytype/

# Cython debug symbols
cython_debug/
