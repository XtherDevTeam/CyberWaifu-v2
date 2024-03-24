# CyberWaifu-v2

[Previous Summary](https://www.bilibili.com/video/BV1rZ421B79N)

A role-playing chatbot based on the Langchain using the Google Gemini Pro model.

English | [Chinese](/README.md)

### Usage

- Currently, the only available frontend is `cmdline interfere frontend`. Click [here](/Usage.md) for tutorials. Click [here](/API.md) to learn more on `web-interfere-api`

**NOTES:**

1. The project once experimentally provided `Python Binding` for `YiriMirai`. Unfortunately, due to the long neglect of `mirai` login, the author failed to verify it successfully.
2. The project experimentally provided support for `fine-tune models`. Unfortunately, it ended in regret due to the lack of support for multi-turn dialogue.
3. Google has not yet opened access to the API for `Gemini 1.5 Pro`. Due to the inadequate capabilities of `Gemini 1.0 Pro`, this is a great regret for the project.
4. `web-interfere-api` is now trending towards availability and can be used in conjunction with `CyberWaifu-V2 Mobile`.

### Principle

To save tokens and enhance the flexibility of the character, CyberWaifu-v2 adopts the following architecture:

- Each conversation initializes a `conversation.ConversationMemory` object to store conversation memories. After the conversation ends, the model is called to summarize the conversation content in the first person as the character and merge it into the character's memory, rather than inheriting all the conversation content to the next conversation.
- Character configuration includes character memory, character `Prompt`, and character name. These pieces of information are passed into the model as `SystemMessage` during the initialization stage of the conversation.

### Tasks

- Improve frontend
- Modify DataProvider into singleton