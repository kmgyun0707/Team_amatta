from setuptools import find_packages, setup

package_name = 'amatta'

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
    maintainer_email='lee74785764@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'move = amatta.move_test:main',
            'move_brute = amatta.move_test_brute:main',
            'visited = amatta.visited_history_patrol:main',
            'lost = amatta.lost_spot_patrol:main',
        ],
    },
)
