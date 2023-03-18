import openai
import os
import json

dir = os.path.abspath(__file__ + "/../")
prompt_name = "starting-prompt.txt"
json_name = "jsons/chat.json"

class Chatbot:
    def __init__(
        self,
        api_key: str,
        engine: str = "gpt-3.5-turbo", #gpt-3.5-turbo
        temperature: float = 1.0,
        system_prompt: str = None,
    ) -> None:

        self.engine = engine
        openai.api_key = api_key
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.conversation = []

    def ChatConversation(self, conversation):
        response = openai.ChatCompletion.create(
            model = self.engine,
            messages = conversation
        )
        conversation.append({"role": response.choices[0].message.role, "content": response.choices[0].message.content})
        return conversation
    
    def reset(self) -> None:
        self.conversation.append({"role": "system", "content": self.system_prompt})

    def save(self) -> None:
        with open(os.path.join(dir, json_name), "w", encoding = "UTF-8") as f:
            json.dump(self.conversation, f, indent=2)
    
    def load(self) -> None:
        with open(os.path.join(dir, json_name), encoding = "UTF-8") as f:
            self.conversation = json.load(f)
    
    def addConversation(self, message: str, role: str) -> None:
        self.conversation.append({"role": role, "content": message})
    
    def ask(self, message: str) -> str:
        self.addConversation(message = message, role = "user")
        response = self.ChatConversation(self.conversation)
        return (response[-1]["content"])