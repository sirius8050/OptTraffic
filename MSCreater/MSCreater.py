import os

__package__ = 'MSCreater'

from deploy.deployment import CreateDeployment
from deploy.RouteGenerater import CreateService
from yaml_read.YamlParser import generate


def main():
    generate('./yaml_read/file/', './yaml_read/temp/', 'social-network')
    # CreateDeployment('./yaml/temp/YamlDeployment.yaml')
    # CreateService('./yaml/temp/YamlService.yaml')


if __name__ == "__main__":
    main()
