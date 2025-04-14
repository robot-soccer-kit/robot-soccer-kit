import setuptools
import os, sys

with open("README.md", "r") as fh:
    long_description = fh.read()


def package_files(directory):
    paths = []
    for path, directories, filenames in os.walk(directory):
        for filename in filenames:
            if "__pycache__" not in path:
                paths.append(os.path.join("..", path, filename))
    return paths


setuptools.setup(
    name="robot_soccer_kit",
    version="2.4.2",
    author="Rhoban team",
    author_email="team@rhoban.com",
    description="Robot Soccer Kit",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/rhoban/robot-soccer-kit/",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: Free for non-commercial use",
        "Operating System :: OS Independent",
    ],
    keywords="robot holonomic omniwheel ssl sct robocup junior soccer standard localized tracking",
    install_requires=["numpy", "pyzmq", "pyyaml", "astar"],
    extras_require={
        # Game controller extra requirements
        "gc": ["pyserial", "flask", "flask-cors", "waitress", "opencv-contrib-python"],
    },
    include_package_data=True,
    package_data={"": package_files("rsk")},
    python_requires=">=3.6",
)
