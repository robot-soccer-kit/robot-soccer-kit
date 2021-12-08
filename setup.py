import setuptools
import os

with open("README.md", "r") as fh:
    long_description = fh.read()

def package_files(directory):
    paths = []
    for (path, directories, filenames) in os.walk(directory):
        for filename in filenames:
            if '__pycache__' not in path:
                paths.append(os.path.join('..', path, filename))
    return paths

setuptools.setup(
    name="junior-ssl",
    version="0.2.8",
    author="Rhoban team",
    author_email="team@rhoban.com",
    description="Junior SSL - An omniwheel soccer setup",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/rhoban/junior-ssl/",
    packages=setuptools.find_packages(),
    scripts=['jssl-gc'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: Free for non-commercial use",
        "Operating System :: OS Independent",
    ],
    keywords="robot holonomic omniwheel ssl robocup junior soccer standard localized tracking",
    install_requires=[
        "numpy",
        "zmq",
    ],
    extras_require={
        'gc': [ # Game controller extra requirements
            "pyserial",
            "pyqt5",
            "pyqtwebengine",
            "opencv-python-headless",
            "opencv-contrib-python-headless"
        ]
    },
    include_package_data=True,
    package_data={"": package_files("jssl")},
    python_requires='>=3.6',
)
