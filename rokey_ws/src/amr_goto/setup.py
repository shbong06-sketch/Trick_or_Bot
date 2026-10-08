from setuptools import setup

package_name = 'amr_goto'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='mingja',
    maintainer_email='codesorryy@gmail.com',
    description='웹캠 car 좌표를 받아 AMR을 car 앞 1.2 m까지 이동',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'amr_goto_car = amr_goto.amr_goto_car:main',
        ],
    },
)
