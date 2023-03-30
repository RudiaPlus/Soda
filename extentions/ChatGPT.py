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
        temperature: float = 0.6,
        system_prompt: str = None
    ) -> None:

        self.engine = engine
        openai.api_key = api_key
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.conversation = []

    def ChatConversation(self, conversation):
        response = openai.ChatCompletion.create(
            temperature = self.temperature,
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
    
class Imakita:
    def __init__(
        self,
        api_key: str,
        engine: str = "gpt-3.5-turbo", #gpt-3.5-turbo
        temperature: float = 0.4
    ) -> None:

        self.engine = engine
        openai.api_key = api_key
        self.temperature = temperature
        
        self.messages = [
            {"role": "system", "content": "あなたは会話文を3行に敬語を使って要約する人です。1行につき1文までとし、必ず3行に収めてください。"},
            {"role": "system", "content": "あなたに与えられる会話文は「[名前]#[ID]:[メッセージ]」の形式です"},
        ]
        
    def imakita(self, texts):
        for text in texts:
            self.messages.append({"role": "user", "content": text})

        response = openai.ChatCompletion.create(
            model = self.engine,
            temperature = self.temperature,
            messages = self.messages
        )
        return (response["choices"][0]["message"]["content"])