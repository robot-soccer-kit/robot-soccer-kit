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


if sys.platform.startswith("win"):
    opencv_version = "opencv-contrib-python<4.7"
else:
    opencv_version = "opencv-contrib-python"

setuptools.setup(
    name="robot-soccer-kit",
    version="2.1.4",
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
    install_requires=["numpy", "pyzmq", "pyyaml"],
    extras_require={
        "gc": ["pyserial", "flask", "flask-cors", "waitress", opencv_version],  # Game controller extra requirements
    },
    include_package_data=True,
    package_data={"": package_files("rsk")},
    python_requires=">=3.6",
)
