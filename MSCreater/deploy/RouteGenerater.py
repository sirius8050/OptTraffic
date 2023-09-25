import os
# 路由是先匹配一个service，然后匹配使用哪个Pod的标签。

def CreateService(FilePath):
    os.system("kubectl apply -f " + FilePath)