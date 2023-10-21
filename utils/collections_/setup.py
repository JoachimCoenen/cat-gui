from setuptools import setup
from Cython.Build import cythonize
import pathlib

buildFolderPath = pathlib.Path(__file__).parent.absolute() / 'build'
forceRebuld = not buildFolderPath.exists()

setup(
    name='Utils Collections',
    package_dir={'Cat.utils.collections_': ''},
    ext_modules=cythonize(
        [
            "orderedmultidictBase.pyx",
        ],
        force=forceRebuld,
        language_level=3,
        annotate=True,
        # nthreads=4,
    ),
    zip_safe=True,
)