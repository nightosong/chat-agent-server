import logging
from logging.handlers import RotatingFileHandler

# 配置日志系统
logger = logging.getLogger("chat_server")
logger.setLevel(logging.DEBUG)

# 定义日志格式
formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d - %(funcName)s()]- %(message)s"
)

# 创建文件处理器，设置日志轮转
file_handler = RotatingFileHandler(
    "logs/chat_server.log", maxBytes=1024 * 1024 * 5, backupCount=5
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

# 创建控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# 将处理器添加到日志记录器
logger.addHandler(file_handler)
logger.addHandler(console_handler)
