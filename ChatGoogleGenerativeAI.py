from typing import Any, Literal
import google.generativeai as genai
from google.generativeai.types.safety_types import HarmBlockThreshold, HarmCategory
from google.auth.credentials import Credentials
import PIL.Image
import os


class BaseMessage():
    def __init__(self, role: str, content_type: str, content : str):
        self.role = role
        self.content_type = content_type
        self.content = content
    
    def getRole(self):
        return self.role
    
    def getContent(self):
        return self.content


class AIMessage(BaseMessage):
    def __init__(self, content: str):
        super().__init__('model', 'text', content)
        
    def getRole(self):
        return self.role
    
    def getContent(self):
        return self.content
    
    def __str__(self):
        return self.content
    
class HumanMessage(BaseMessage):
    def __init__(self, content: str | list[str], content_type: str = 'text'):
        super().__init__('human', content_type, content)
        
    def getRole(self):
        return self.role
    
    def getContent(self):
        return self.content
    
    def __str__(self):
        return self.content
    
    def json_content(self):
        return {
            "role": self.role,
            "content_type": self.content_type,
            "content": self.content
        }


class ChatGoogleGenerativeAI():
    def __init__(self, model: str, convert_system_message_to_human: bool, temperature: float, safety_settings: Any = {}, credentials: Credentials | None = None, system_prompt : str | None = None) -> None:
        self.model : genai.GenerativeModel | None = None
        self.chat_session : genai.ChatSession | None = None
        self.chat_history = []
        if credentials is None:
            genai.configure(os.environ.get('GOOGLE_API_KEY'))
            self.model = genai.GenerativeModel(model, safety_settings=safety_settings, temperature=temperature, safety_settings=safety_settings, system_instruction=system_prompt)
        else:
            self.model = genai.GenerativeModel(model, safety_settings=safety_settings, temperature=temperature, safety_settings=safety_settings, credentials=credentials, system_instruction=system_prompt)
    
    def invoke(self, msg: BaseMessage | list[BaseMessage]) -> str:
        if msg is BaseMessage:
            self.chat_history.append(msg)
        else:
            self.chat_history = msg
            
        if self.chat_session is None:
            # initiate a new chat
            self.chat_session = self.model.start_chat(self.chat_history)
            self.chat_session.send_message(msg)
            
        
        