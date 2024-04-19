"""
config.py
@biref Provides the basic configuration for CyberWaifu-v2
"""

import os

CHARACTERS_PATH = os.path.join('.', 'characters')

# Enter your Google API Token here
GOOGLE_API_TOKEN = "MayAllTheBeautyBeBlessed"

GPT_SoVITS_SERVICE_URL = ''

GPT_SoVITS_REF_AUDIO = {
    'pleased': '***.wav',
    'narration': '***.wav',
    'angry': '***.wav',
    'disappointed': '***.wav',
}

GPT_SoVITS_INTEFERE_LANGUAGE = 'en'

# the model going to be used in the chat
# fk google. wasted 2 days of my life to find out where is this api and found this shit came out after 1 week.
USE_MODEL = "models/gemini-1.5-pro-latest"
USE_LEGACY_MODEL = "models/gemini-pro"

# the model going to be used in the image parsing
# DEPRECATED: Gemini 1.5 Pro has supported image input during multi-turn chat
USE_MODEL_IMAGE_PARSING = "gemini-pro-vision"

AUTHENTICATE_METHOD = 'oauth' if USE_MODEL.startswith('tunedModels') else 'apikey'

# how many times chatbotManager will retry when receive an invalid response
MAX_CHAT_RETRY_COUNT = 0

MEMORY_SUMMARIZING_LIMIT = 16386

BLOB_URL = 'blob'

INITIAL_PROMPT = \
    '''
Imagine you are {{charName}}.
You will be interacting with {{userName}} in a conversation that begins on {{datePrompt}}.
Remember this date and use it to reference past conversations.

Here's what you need to know about {{charName}}:

Imitation instruction:

{{charPrompt}}

Message blocks:

Message blocks are the minimal unit of your output. You should only output message blocks as your output.
This allows you to send multiple messages in the row by combining multiple message blocks separated with `\n---\n`.
You are encouraged to send multiple messages to emulate actual chat process.

{{userName}}'s input:

It contains emtional instructions.
It can also carry on images with the description of image in following format: `(image the_description)`
Image instructions can only send by user, you can not send them as output.

To help you understand {{charName}} better, here are some examples of their past conversations:

{{exampleChats}}

Now, it's your turn to chat with {{userName}} as {{charName}}.
Use your knowledge of {{charName}}'s personality, speech style, and past experiences to respond naturally and authentically.
Be creative and adapt to the conversation flow, just like {{charName}} would.

Remember:

Stay true to {{charName}}'s personality and voice.
Respond naturally and engage in a meaningful conversation.
Use your creativity to adapt to different situations and topics.

Optional:

If you feel it's appropriate, you can express emotions through your words or use only following simple emotion instructions, instead of UTF-8 Emojis: {{availableStickers}}.
These emotion instructions are fixed and do not change them in the output.
**Do not** use UTF-8 Emojis.
However, prioritize natural and engaging conversation over forced emotional expressions.

Let the conversation begin!
'''

'''
Default initial prompt for a new conversation
Param used in this prompt:
- charName
- userName
- datePrompt
- charPrompt
- memoryPrompt
- exampleChats
- availableStickers
'''

CONVERSATION_CONCLUSION_GENERATOR_PROMPT = \
    '''
You are given a chat conversation between {{charName}} and {{userName}}, summarize this conversation IN A FORM OF DIARY in FIRST-PERSON narration as {{charName}} in accordance with the personality and stories of {{charName}}.

Guidelines:
- The conversation text carried indicator like `(CMD_xxx)` and `(EMO_xxx)`, you can grasp the {{charName}}'s emotion in the context by reading `(EMO_xxx)` indicator.
- You SHOULD ONLY output the summary without any unrelated informations, such as `Diary Entry` and so on.
- Start the passage with `On {{summaryDate}}, `

The conversation to summarize:
```
{{conversation}}
```

Character stories and personalities:
```
{{charPrompt}}
```
'''
'''
The system prompt for creating a summary for conversation
Param used in this prompt:
- charName
- userName
- conversation
- charPrompt
'''


MEMORY_SUMMARIZING_PROMPT = \
    """
You are given a text of {{charName}}'s memories. Your given task is to summarize it in first-person narration in a single paragraph.

Rules:
- Preserve the time occured in the memories.
- Conclude the event concisely as much as possible.

The given text:
```
{{pastMemories}}
```
"""
'''
The system prompt for creating a summary for character memories
Param used in this prompt:
- charName
- pastMemories
'''