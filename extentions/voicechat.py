from pyvcroid2 import pyvcroid2
import os

def speak(text: str):
    try:
        dir = os.path.abspath(__file__ + "\\..\\")
        voice_name = "voiceroid\\VOICEROID2"
        with pyvcroid2.VcRoid2(install_path = os.path.join(dir, voice_name)) as voice:
            # Load language library
            lang_list = voice.listLanguages()
            if "standard" in lang_list:
                voice.loadLanguage("standard")
            elif 0 < len(lang_list):
                voice.loadLanguage(lang_list[0])
            else:
                raise Exception("No language library")
    
            # Load Voice
            voice_list = voice.listVoices()
            if 0 < len(voice_list):
                voice.loadVoice(voice_list[0])
            else:
                raise Exception("No voice library")
            
            # Set parameters
            voice.param.volume = 1.00
            voice.param.speed = 1.2
            voice.param.pitch = 1.1
            voice.param.emphasis = 0.95
            voice.param.pauseMiddle = 80
            voice.param.pauseLong = 100
            voice.param.pauseSentence = 100
            voice.param.masterVolume = 1.123
            
            filepath = "voiceroid\\"
            filename = "voice.wav"
            file = filepath + filename
            speech, tts_events = voice.textToSpeech(text)
        
            with open(file, mode = "wb") as f:
                f.write(speech)
            return f"{filepath}voice.wav"
    except Exception as e:
        print(f"【voicechat.speak】エラー：{e}")