# CyberWaifu-v2

[前情提要](https://www.bilibili.com/video/BV1rZ421B79N) | [Devpost](/Devpost.md) 

一个基于 Langchain 使用 Google Gemini Pro 模型的角色模拟聊天机器人。

An Character Roleplay Chatbot based on Google Gemini Pro.

[English](/docs/README_en.md) | Chinese

### 使用

- 目前可用的前端只有 `cmdline interfere frontend`，点击 [此处](Usage.md) 查看教程。

**NOTES:** 

1. 该项目曾试验性地提供了 `YiriMirai` 的 `Python Binding`，很遗憾，由于 `mirai` 登陆年久失修，作者并未能成功检验。
2. 该项目试验性地提供了对于 `fine-tune models` 的支持，由于不支持多轮对话，以遗憾告终。
3. <s>目前 Google 仍未开放对 `Gemini 1.5 Pro` 的 API 访问，由于 `Gemini 1.0 Pro` 能力的欠缺，这对于该项目是一个极大的遗憾。</s> 项目开发者在被迫吃了半个月的矢之后，被告知已开放 API 访问。
4. `web-interfere-api` 现已趋于可用，可配合 `CyberWaifu-V2 Mobile` 使用

### 原理

为了节省 Token 和提升角色的灵活性，CyberWaifu-v2 采用了如下架构：

- 每次对话会初始化一个 `conversation.ConversationMemory` 对象，用于存储对话记忆，在对话结束后会调用模型以角色为第一人称总结对话内容，并调用模型合并到角色记忆，而不是将对话内容全部继承至下一次对话。
- 角色配置分为角色记忆、角色 `Prompt` 和角色名称，这些信息会在初始化对话阶段作为 `SystemMessage` 传入模型。

### Tasks

- 完善前端
- DataProvider 改单例
- 当点击发送按钮时，等待五秒，再发送请求，若用户继续打字，则重置等待时间。允许用户单次发送多条信息。
- 加入TTS，允许模型发送音频。
- 改掉新建角色的前端，太几把丑了