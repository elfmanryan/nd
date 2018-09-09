from setuptools import setup, find_packages, Extension
from Cython.Distutils import build_ext
import numpy
import cython_gsl

# from Cython.Compiler.Options import get_directive_defaults
# directive_defaults = get_directive_defaults()
# directive_defaults['linetrace'] = True
# directive_defaults['binding'] = True

ext_modules = [
    Extension("geo._omnibus", ["geo/_omnibus.pyx"],
              libraries=cython_gsl.get_libraries(),
              library_dirs=[cython_gsl.get_library_dir()],
              include_dirs=[cython_gsl.get_cython_include_dir()]),
            #   define_macros=[('CYTHON_TRACE', '1')]),
    Extension("geo._warp", ["geo/_warp.pyx"])
]

setup(
    name='geotools',
    packages=find_packages(),
    cmdclass={'build_ext': build_ext},
    ext_modules=ext_modules,
    include_dirs=[
        numpy.get_include(),
        cython_gsl.get_include()
    ],
    install_requires=[
        "numpy",
        "scipy",
        "xarray",
        "dask",
        "cython",
        "lxml",
        "gdal",
        "pandas",
        "python-dateutil",
        "scikit-image",
        "matplotlib",
        "affine",
        "cython_gsl",
        "opencv"
    ]
)
