import os
import sys

__package__ = 'MSCreater'

from MSCreater.deploy.deployment import CreateDeployment
from MSCreater.deploy.RouteGenerater import CreateService
from MSCreater.yaml_read.YamlParser import generate


def main(argv):
    if len(argv) > 2:
        if argv[2] == 'delete':
            os.system('kubectl delete -f ./MSCreater/yaml_read/temp/'+argv[1]+'_YamlDeployment.yaml')
            os.system('kubectl delete -f ./MSCreater/yaml_read/temp/' + argv[1] + '_YamlService.yaml')
            if 'hotel' in argv[1]:
                os.system('kubectl delete -f ./MSCreater/yaml_read/temp/' + argv[1] + '_YamlOthers.yaml')
            return
        if argv[2] == 'create':
            generate('./MSCreater/yaml_read/file/'+argv[1]+'.yaml', './MSCreater/yaml_read/temp/', argv[1])
    if 'hotel' in argv[1]:
        CreateService('./MSCreater/yaml_read/temp/' + argv[1] + '_YamlOthers.yaml')
    CreateDeployment('./MSCreater/yaml_read/temp/'+argv[1]+'_YamlDeployment.yaml')
    CreateService('./MSCreater/yaml_read/temp/'+argv[1]+'_YamlService.yaml')
    


if __name__ == "__main__":
    main(sys.argv)


