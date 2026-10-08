from setuptools import setup

package_name = 'amr_controller'

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
    maintainer='TGS10218',
    maintainer_email='codesorryy@gmail.com',
    description='AMR Controller: 웹캠이 보낸 car 좌표로 Nav2 이동',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'goto_car = amr_controller.goto_car_node:main',
        ],
    },
)
