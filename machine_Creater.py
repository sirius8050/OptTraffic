import os
import sys

__package__ = 'MSCreater'

from MSCreater.deploy.deployment import CreateDeployment
from MSCreater.deploy.RouteGenerater import CreateService
from MSCreater.yaml_read.YamlParser import generate


def main(argv):
    path = sys.argv[3]
    if len(argv) > 2:
        if argv[2] == 'delete':
            os.system('kubectl delete -f ' + path + 'temp/' + argv[1] + '_YamlDeployment.yaml')
            os.system('kubectl delete -f ' + path + 'temp/' + argv[1] + '_YamlService.yaml')
            if 'hotel' in argv[1]:
                os.system('kubectl delete -f ' + path + argv[1] + '_YamlOthers.yaml')
            return
        if argv[2] == 'create':
            generate(path + argv[1]+'.yaml', path + 'temp/', argv[1], machine=sys.argv[4])
    CreateDeployment(path + 'temp/' + argv[1]+'_YamlDeployment.yaml')
    CreateService(path + 'temp/' + argv[1]+'_YamlService.yaml')
    if 'hotel' in argv[1]:
        CreateService(path + 'temp/' + argv[1] + '_YamlOthers.yaml')


if __name__ == "__main__":
    main(sys.argv)


