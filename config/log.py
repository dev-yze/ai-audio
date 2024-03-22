import logging
import os


#=============================日志配置===================================
# 设置日志的记录等级
logging.basicConfig(level=logging.INFO)
# 创建日志记录器，指定日志的最低输出级别
logger = logging.getLogger("my_logger")
logger.setLevel(logging.INFO)
# 创建日志记录的格式，包括进程ID、方法名、请求参数
formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(process)d] - %(funcName)s - %(message)s')

# 创建一个日志处理器，用于将日志输出到控制台
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# 创建一个日志处理器，用于将日志输出到文件
if not os.path.exists('logs'):
    os.makedirs('logs')
file_handler = logging.FileHandler('logs/app.log')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)