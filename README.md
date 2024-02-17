# CyberWaifu-v2

[前情提要](https://www.bilibili.com/video/BV1rZ421B79N)

### 原理

为了节省 Token 和提升角色的灵活性，CyberWaifu-v2 采用了如下架构：

- 每次对话会初始化一个 `conversation.ConversationMemory` 对象，用于存储对话记忆，在对话结束后会调用模型以角色为第一人称总结对话内容，并调用模型合并到角色记忆，而不是将对话内容全部继承至下一次对话。
- 角色配置分为角色记忆、角色 `Prompt` 和角色名称，这些信息会在初始化对话阶段作为 `SystemMessage` 传入模型。