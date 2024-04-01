# 一些同学有跑COFFE的需求，这里写一下教程。--沈宇航
# 跑COFFE需要python2.7和hspice，这里介绍两种方法
1. 使用配置有python2.7和hspice的docker镜像，服务器112、114和115上面使用docker images命令可以查看已经安装的镜像，名称带有hspice或者coffe的镜像都是可以使用的。注意使用docker镜像生成容器的时候，需要设置mac-address和host以激活里面的hspice，这部分查gitlab教程，遇到问题找热心的李震博士。另外，不建议使用这种方法！！！一是服务器的docker镜像已经滥用了，二是配置起来也比较麻烦。
2. 使用学院集群，以下介绍使用方法：
## 登录学院集群，参考相关文档
## 配置hspice环境，首先命令行输入csh切换到相应的shell环境（默认是bash），之后使用source /apps/EDAs/cshrc/cshrc_syn成功配置hspice2013，这样便可以使用hspice2013了
## 上传COFFE项目，解压，先使用python2 coffe.py arch_file/path initial_sizes/path（这个自己参考代码中参数设置）测试coffe是否可以跑起来，之后请使用bsub提交job（参考相关文档）
