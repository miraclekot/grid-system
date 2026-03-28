# setup.py
from setuptools import setup, find_packages

setup(
    name="grid-system-master-node",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "aiohttp",
        "grid-system-common",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "master-node=master_node.main:main",
        ],
    },
)