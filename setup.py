from setuptools import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="podme_api-bendikrb",
    version="0.0.1",
    description="A client library for using the podme.com web API.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bendikrb/podme_api",
    author="Bendik R. Brenne",
    author_email="bendik@brenne.nu",
    license="MIT",
    packages=["podme_api"],
    install_requires=[
        "PyYAML",
        "requests",
        "youtube-dl",
        "simplejson",
    ],
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.6",
)
