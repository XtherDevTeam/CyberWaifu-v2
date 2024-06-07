import mimetypes
from typing import Any
import google.generativeai as genai



def Message(role: str, content: str, content_type: str) -> dict[str, str]:
    return {
        'role': role,
        'content': content,
        'content_type': content_type
    }


def AIMessage(content: str) -> dict[str, str]:
    return Message('model', content, 'text')


def HumanMessage(content: str, content_type: str = 'text') -> dict[str, str]:
    return Message('user', content, content_type)


class ChatGoogleGenerativeAI():
    def __init__(self, model: str, temperature: float = 0.9, safety_settings: Any = None, system_prompt: str | None = None, tools: list[function] = []) -> None:
        self.model: genai.GenerativeModel = genai.GenerativeModel(model_name=model, system_instruction=system_prompt, safety_settings=safety_settings, generation_config={
            'temperature': temperature,
        }, tools=tools)
        self.chat_session: genai.ChatSession | None = None

    def initiate(self, begin_msg: list[dict[str, str]]) -> str:
        if self.chat_session is None:
            self.chat_session = self.model.start_chat()
        # initiate chat with beginning message
        return self.chat_session.send_message(begin_msg).text

    def chat(self, user_msg: list[dict[str, str]]) -> str:
        if self.chat_session is None:
            raise ValueError(f'{__name__}: Chat session not initiated')
        # chat with user message
        return self.chat_session.send_message(user_msg).text