from setuptools import setup, find_packages

setup(
    name="vtf-cli",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.0",
        "requests>=2.28",
        "pyyaml>=6.0",
    ],
    extras_require={
        "dev": ["pytest", "requests-mock"],
    },
    entry_points={
        "console_scripts": [
            "vtf=vtf.cli:cli",
        ],
    },
)
