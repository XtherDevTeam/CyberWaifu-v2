"""
conversation.py
Provides class ConversationMemory
"""

import config
import models
import memory
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


class ConversationMemory:
    """
    ConversationMemory
    @brief accept userName, and character memory object, and initialize converation history for chatbot instance
    """

    def __init__(self, userName, char: memory.Memory) -> None:
        self.memory = []
        self.userName = userName
        self.char = char

    def getConversation(self) -> list[(HumanMessage | AIMessage | SystemMessage)]:
        return self.memory

    def storeUserInput(self, input: HumanMessage) -> str:
        self.memory.append(input)

    def storeBotInput(self, input: AIMessage) -> None:
        """
        for i in input.content.split('(OPT_MULTI_CUR_MSG_END)'):
            self.memory.append(AIMessage(i.strip()))
        """
        self.memory.append(input)
            

    def summarize(self) -> str:
        realDialogue = []
        for i in self.memory:
            # Feat: convert new api message to langchain message
            print(i)
            if i['role'] == 'model':
                for j in i['content'].split('---'):
                    realDialogue.append(AIMessage(content=j.strip()))
            elif i['role'] == 'human':
                realDialogue.append(HumanMessage(i['content']))
            
        conversation = ""
        for i in realDialogue:
            if isinstance(i, HumanMessage):
                conversation += f'''
{self.userName}:
{i.content}
'''
            elif isinstance(i, AIMessage):
                conversation += f'''
{self.char.getCharName()}:
{i.content}
'''
        llm = models.BaseModelProvider()
        c = llm.invoke(
            [SystemMessage(models.PreprocessPrompt(config.CONVERSATION_CONCLUSION_GENERATOR_PROMPT, {
                'charName': self.char.getCharName(),
                'userName': self.userName,
                'conversation': conversation,
                'charPrompt': self.char.getCharPrompt(),
                'summaryDate': models.TimeProider()
            })), HumanMessage("")]
        ).content
        print(c)
        return c
