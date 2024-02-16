"""
conversation.py
Provides packages for model operating
"""

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import config
import time


def TimeProider() -> str:
    return time.strftime('%Y-%m-%d %I:%M', time.localtime())


def DateProider() -> str:
    return time.strftime('%Y-%m-%d', time.localtime())


def PreprocessPrompt(originalPrompt: str, tVars):
    for i in tVars:
        originalPrompt = originalPrompt.replace('{{' + i + '}}', tVars[i])
        
    return originalPrompt


def BaseModelProvider() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=config.USE_MODEL, convert_system_message_to_human=True)


def MemoryMergingModel(userName: str, charName: str, summary: str, pastMemories: str) -> AIMessage:
    llm = BaseModelProvider()
    return llm.invoke([
        SystemMessage(content=PreprocessPrompt(
            config.MEMORY_MERGING_PROMPT,
            {
                'userName': userName,
                'charName': charName,
                'summary': summary,
                'summaryDate': DateProider(),
                'pastMemories': pastMemories
            }
        )),
        HumanMessage("")
    ])
