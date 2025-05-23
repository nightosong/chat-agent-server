# DeepResearch AI Service
## 项目介绍

该项目是DeepResearch研究项目，主要用于提供相关的AI服务，通过FastAPI框架构建RESTful API，方便与其他系统进行交互。

## 项目背景
本项目旨在为DeepResearch研究提供高效、稳定的服务支持，利用先进的AI技术处理和分析相关数据。

## 项目结构
```plaintext
agents:
    - deep_research_v2.py
    - deep_research_v3.py

modules:
    - ai: 包含AI相关的模块，如模型加载、推理等功能。
    - web: 包含WebSearch相关的模块，探索多种网页搜索方式。

services:
    - api_deep_research: 提供DeepResearch相关的API接口。

main.py: 启动服务的入口文件
requirements.txt: 项目依赖
```

## 功能模块
### LLM
该模块集成了大语言模型，用于处理自然语言相关的任务，如文本生成、问答系统等。

### DeepResearch
该模块专注于深度研究相关的功能，通过调用LLM模块和其他工具，对输入的数据进行深入分析。

## 启动服务
在 `main.py` 中定义了 FastAPI 应用。使用以下命令启动服务：
```bash
virtualenv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
# uvicorn 启动服务
uvicorn main:app --host 0.0.0.0 --port 8020 --reload
# gunicorn 启动服务
gunicorn main:app -k uvicorn.workers.UvicornWorker --workers 4 --bind 0.0.0.0:8020
```

## API 文档
### DeepResearch接口
- **URL**: `/api/deep_research`
- **方法**: `POST`
- **参数**: 
  - `query`: 需要进行深度研究的查询内容。
  - `engine`: 选择使用的引擎,选项有`searxng`,`firecrawl`,`playwright`。
```python
    def test_deep_research():
        ...
```
