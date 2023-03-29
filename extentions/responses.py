#from revChatGPT.V1 import AsyncChatbot
from extentions import ChatGPT, config, log
import os

logger = log.setup_logger(__name__)

"""async def getresponse(message) -> str:
    try:
        chatbot = AsyncChatbot(config = {"access_token": config.openAI_token}, conversation_id = "67bcc8d1-5c4a-48e3-9d0a-d38a64a8b208")
        response = ""
        async for line in chatbot.ask(message):
            response = line["message"]
        return response
    except Exception as e:
        print(f"【responses.get_response】エラー：{e}")"""


async def get_response(message, reset: bool) -> str:
  try:
    prompt_dir = os.path.abspath(__file__ + "/../../")
    prompt_name = "starting-prompt.txt"
    with open(os.path.join(prompt_dir, prompt_name), encoding="UTF-8") as f:
      prompt = f.read()
    chatbot = ChatGPT.Chatbot(api_key=config.openAI_key,
                              temperature=0.6,
                              system_prompt=prompt)
    if reset == True:
      chatbot.reset()
      chatbot.save()
      return ("リセットしました")

    chatbot.load()
    response = chatbot.ask(message)
    chatbot.save()
    return response
  except Exception as e:
    logger.info(f"【responses.get_response】エラー：{e}")
