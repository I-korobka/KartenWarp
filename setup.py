# setup.py
import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="KartenWarp",
    version="0.4.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="KartenWarp - A tool for image transformation using feature points.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/I-korobka/KartenWarp",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=[
        "PyQt5",
        "numpy",
        "opencv-python",
    ],
    entry_points={
        'console_scripts': [
            'kartenwarp=main:main',
        ],
    },
)
