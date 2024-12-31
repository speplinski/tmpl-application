from setuptools import setup, find_namespace_packages

setup(
    name="tmpl_app",
    version="1.0.0",
    packages=find_namespace_packages(include=['*']),
    install_requires=[
        'numpy',
        'opencv-python',
        'depthai',           # For OAK-D camera
        'psutil',            # For system monitoring
        'av>=10.0.0',        # For video handling
        'Pillow>=10.0.0',    # For image processing 
        'pysdl2>=0.9.16',    # For display
        'pysdl2-dll>=2.28.0' # SDL2 binaries
    ],
    python_requires='>=3.7',
)