from glob import glob

from setuptools import find_packages, setup

package_name = 'tob_perception'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
        ('share/' + package_name + '/models', glob('models/*.pt')),
    ],
    install_requires=[
        'setuptools',
        'numpy',
        'torch',
        'ultralytics',
    ],
    zip_safe=True,
    maintainer='may',
    maintainer_email='maymayko9559@gmail.com',
    description='ROS2 package for detecting pumpkins in RGB images from Boo OAK-D camera.',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'boo_detector_node = tob_perception.boo_detector_node:main',
            'webcam_detector_node = tob_perception.webcam_detector_node:main',
        ],
    },
)
