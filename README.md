
## 仓库地址
https://github.com/dev-yze/ai-audio.git


## 环境搭建
```shell
conda create -n ai-media python=3.9
conda activate ai-media
pip install -r requirements.txt
```


## 项目运行
```
python app.py -frp -initdb -model large
```
* `-frp` 运行内网穿透
* `-initdb` 重新初始化数据库
* `-model` 加载whisper中指定大小模型,如['tiny', 'base', 'small', 'medium', 'large']