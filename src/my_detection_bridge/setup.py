from setuptools import find_packages, setup

package_name = 'my_detection_bridge'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='rokey',
    maintainer_email='abbeyroad1027@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={  
        'console_scripts': [
            'bridge_node = my_detection_bridge.db_bridge_node_2:main',
            'nav_bridge_node = my_detection_bridge.nav_bridge_node:main',
            'test_node = my_detection_bridge.detection_test_node_2:main',
            'detection_integrated = my_detection_bridge.detection_integrated_test:main',
        ],
    },
)
