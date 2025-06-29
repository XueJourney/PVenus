# PVenus
PVenus ———— 一个多模态聊天机器人(原本要做虚拟女友的，结果发现跑题了)

## 功能特色

- 💬 支持自然语言对话，智能理解与个性化回复
- 🖼️ 支持图片分析，自动识别图片内容并生成描述
- 🗣️ 语音合成与多音色选择，AI 可用多种声音与语速朗读回复
- 🧠 永久记忆系统，AI 可记住重要信息并随时调用
- 📝 聊天历史保存，支持上下文连续对话
- 🖥️ 提供 CLI（命令行）与 GUI（图形界面）两种交互方式

## 安装与运行

### 依赖环境

- Python 3.8+
- 推荐使用 [conda](https://docs.conda.io/) 或 venv 虚拟环境

### 安装依赖

```sh
pip install -r requirements.txt
```

### 启动 GUI 版

```sh
python GUI/mainGUI.py
```

### 启动 CLI 版

```sh
python CLI/mainCLI.py
```

## 配置说明

首次运行时会提示输入以下信息：

- SiliconFlow Key（用于多模态与语音服务）
- OpenAI Key（用于 GPT-4o 智能对话）
- OpenAI API 网关（可选，默认官方）

用户偏好（职业、称呼、回复风格等）也可在设置界面或 CLI 交互中自定义。

配置、记忆与聊天记录均保存在 `data/` 目录下（GUI）或当前目录（CLI）。

## 依赖第三方服务

- [SiliconFlow](https://www.siliconflow.cn/) 多模态与语音 API
- [OpenAI](https://platform.openai.com/) GPT-4o 智能对话

## 开源协议

本项目采用 MIT License，详见 [LICENSE](LICENSE)。

---

如有建议或问题，欢迎提交 issue 或 PR！