# CyberWaifu-v2

[前情提要](https://www.bilibili.com/video/BV1rZ421B79N)

一个基于 Google Gemini Pro 模型的角色模拟聊天机器人。

An Character Roleplay Chatbot based on Google Gemini Pro.

<s>[Engligh (Still in progress)](#)</s> | Chinese

### 使用

- 目前可用的前端只有 `cmdline interfere frontend`，点击 [此处](Usage.md) 查看教程。

**NOTES:** 该项目曾试验性地提供了 `YiriMirai` 的 `Python Binding`，很遗憾，由于 `mirai` 登陆年久失修，作者并未能成功检验。

### 原理

为了节省 Token 和提升角色的灵活性，CyberWaifu-v2 采用了如下架构：

- 每次对话会初始化一个 `conversation.ConversationMemory` 对象，用于存储对话记忆，在对话结束后会调用模型以角色为第一人称总结对话内容，并调用模型合并到角色记忆，而不是将对话内容全部继承至下一次对话。
- 角色配置分为角色记忆、角色 `Prompt` 和角色名称，这些信息会在初始化对话阶段作为 `SystemMessage` 传入模型。