from glob import glob

from setuptools import setup

package_name = 'detection_alert'

setup(
    name=package_name,
    version='0.2.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # 학습한 YOLO 가중치를 install/detection_alert/share/detection_alert/models/ 에 설치
        ('share/' + package_name + '/models', glob('models/*.pt')),
        # 웹캠 pixel → map 좌표 변환 행렬 (calib_homography가 만듦)
        ('share/' + package_name + '/config', glob('config/*.yaml')),
        # 로봇 없이 맵 + 웹캠 car 좌표를 보는 RViz 설정
        ('share/' + package_name + '/rviz', glob('rviz/*.rviz')),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='TGS10218',
    maintainer_email='codesorryy@gmail.com',
    description='Detection Alert: 고정 웹캠 car 검출 + car의 map 좌표 publish',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'webcam_detector = detection_alert.webcam_detector_node:main',
            'car_locator = detection_alert.car_locator_node:main',
            'calib_homography = detection_alert.calib_homography:main',
            'record_map_points = detection_alert.record_map_points:main',
            'eval_car_point = detection_alert.eval_car_point:main',
            'check_camera = detection_alert.check_camera:main',
            'scenario_test = detection_alert.scenario_test:main',
        ],
    },
)
