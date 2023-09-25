import os


def CreateDeployment(FilePath):
    os.system("kubectl apply -f " + FilePath)